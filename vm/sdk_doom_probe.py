# SPDX-License-Identifier: GPL-3.0-or-later
"""Read-only engine observations while normal input drives the ARM app."""
from pathlib import Path
import re
import shutil
import subprocess
import time
from PIL import Image


class DoomProbe:
    def __init__(self,normal,elf,folder,*,symbols=(),fields=None):
        self.normal=normal;self.elf=elf;self.folder=Path(folder);self.records=[]
        self.symbols=symbols;self.fields=fields or {}
        self.endpoint=Path(normal.channel.socket.getpeername()).parent/'doom-gdb'
        normal.execute('human-monitor-command',{'command-line':'gdbserver unix:'+str(self.endpoint)+',server=on,wait=off'})

    def read(self,label):
        channel=self.normal.channel
        fault=int(channel.command('APP DIAG 9').split()[1]);assert not fault,('app fault',fault,channel.command('APP DIAG 10'))
        player='players[consoleplayer]'
        fields={'state':'gamestate','tics':'gametic','health':player+'.health','menu':'menuactive',
                'message':'messageToPrint','save_entry':'saveStringEnter','save_error':'savegame_error',
                'save_request':'sendsave','action':'gameaction','mouse':'mouseSensitivity','screen':'screenblocks',
                'x':player+'.mo ? '+player+'.mo->x : 0','y':player+'.mo ? '+player+'.mo->y : 0'}
        fields.update(self.fields)
        symbols=[]
        for path in self.symbols:
            quoted=str(Path(path).resolve()).replace('\\','\\\\').replace('"','\\"')
            symbols+=['-ex','add-symbol-file "'+quoted+'"']
        if self.symbols:symbols+=['-ex','set language c++']
        command='printf "DOOM '+','.join(['%d']*len(fields))+'\\n", '+', '.join('('+v+')' for v in fields.values())
        result=subprocess.run([shutil.which('arm-none-eabi-gdb'),'-q','-nx','-batch',str(self.elf.resolve()),
            '-ex','set pagination off',*symbols,'-ex','target remote '+str(self.endpoint),'-ex',command,'-ex','detach'],
            capture_output=True,text=True,timeout=30)
        name=str(len(self.records))+'-'+label+'.log';(self.folder/name).write_text(result.stdout+result.stderr)
        found=re.search(r'^DOOM ([0-9,\-]+)$',result.stdout,re.M)
        assert result.returncode==0 and found,result.stdout+result.stderr
        values=dict(zip(fields,map(int,found[1].split(',')),strict=True))
        values['exited']=int(channel.command('APP DIAG 15').split()[1])!=0
        status=int(channel.command('APP DIAG 21').split()[1]);values['exit_status']=status-2**32 if status>=2**31 else status
        self.records.append({'label':label,'log':name,**values});return values

    def until(self,label,predicate,timeout=180):
        end=time.monotonic()+timeout
        while True:
            value=self.read(label)
            if predicate(value):return value
            assert not value['exited'] and time.monotonic()<end,(label,value)
            time.sleep(.15)

    def capture(self,label):
        path=self.folder/(label+'.ppm');self.normal.execute('screendump',{'filename':str(path)})
        with Image.open(path) as frame:frame.save(path.with_suffix('.png'))

    def save(self,slot=0,*,name=('one','two','three'),confirm=True):
        self.normal.key('num');self.until('save-menu',lambda s:s['menu']==1)
        for _ in range(slot):self.normal.key('down')
        self.normal.key('ok');self.until('save-name',lambda s:s['save_entry']==1)
        for _ in range(24):self.normal.key('backspace')
        for key in name:self.normal.key(key)
        if confirm:self.normal.key('ok')

    def settings(self):
        self.normal.key('minus')
        self.normal.key('back');self.normal.key('down');self.normal.key('ok')
        for _ in range(4):self.normal.key('down')
        self.normal.key('right')
        changed=self.until('settings-changed',lambda s:s['mouse']==8 and s['screen']==9)
        # The platform's Back sends Escape, which closes the whole Doom menu.
        # A second Escape would reopen it and swallow the F10 quit shortcut.
        self.capture('options');self.normal.key('back')
        self.until('options-closed',lambda s:s['menu']==0)
        return changed

    def quit(self,status=0):
        self.normal.key('toolbox');self.until('quit-confirmation',lambda s:s['message']!=0)
        self.normal.key('ok')
        # Configuration commits verify the real large WAD root. Keep observing
        # guest progress with a bounded maintainer workload deadline.
        result=self.until('exit',lambda s:s['exited'])
        assert result['exit_status']==status,result
        self.capture('quit')
