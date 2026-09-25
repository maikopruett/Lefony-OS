# SPDX-License-Identifier: GPL-3.0-or-later
"""Shared embedded desktop renderer; no remote assets or calculator data uploads."""
from html import escape
import json

# Key names are the SDK's Prime matrix contract, not host scancodes.
ROWS = [
    [('symb', 'Symb'), ('plot', 'Plot'), ('num', 'Num'), ('help', 'Help'), ('view', 'View'), ('menu', 'Menu')],
    [('home', 'Home'), ('apps', 'Apps'), ('cas', 'CAS'), ('back', 'Esc'), ('backspace', '⌫')],
    [('xnt', 'x,t,θ,n'), ('fraction', 'a/b'), ('power', 'xʸ'), ('sin', 'sin'), ('cos', 'cos'), ('tan', 'tan')],
    [('ln', 'ln'), ('log', 'log'), ('square', 'x²'), ('toolbox', 'Toolbox'), ('var', 'Vars'), ('units', 'Units')],
    [('alpha', 'Alpha'), ('seven', '7'), ('eight', '8'), ('nine', '9'), ('divide', '÷')],
    [('shift', 'Shift'), ('four', '4'), ('five', '5'), ('six', '6'), ('multiply', '×')],
    [('parenthesis', '( )'), ('one', '1'), ('two', '2'), ('three', '3'), ('minus', '−')],
    [('plusminus', '±'), ('zero', '0'), ('dot', '.'), ('space', 'Space'), ('plus', '+')],
    [('comma', ','), ('ee', 'EEX'), ('ok', 'Enter')],
]


def key(name, label):
    return f'<button type="button" class="key {name}" data-key="{name}" aria-label="{escape(label)}">{escape(label)}</button>'


def page(title, skins=None):
    rows = []
    for index, row in enumerate(ROWS):
        rows.append(f'<div class="key-row cols-{len(row)}">' + ''.join(key(*item) for item in row) + '</div>')
        if index == 1:
            rows.append('<div class="arrows" aria-label="Direction keys">' + ''.join(key(*item) for item in [('up', '↑'), ('left', '←'), ('down', '↓'), ('right', '→')]) + '</div>')
    return (HTML.replace('__SKINS__', json.dumps(skins or []).replace('<', '\\u003c'))
            .replace('__TITLE__', escape(title)).replace('__KEYS__', '\n'.join(rows)))


HTML = r'''<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Lefony Emulator · __TITLE__</title>
<style>
:root{color-scheme:dark;background:#10171c}
*{box-sizing:border-box}html,body,main{width:100%;height:100%;margin:0;overflow:hidden}
main{display:flex;align-items:center;justify-content:center}
canvas{display:block;background:#fff;image-rendering:pixelated;touch-action:none;cursor:crosshair}
.key{user-select:none;touch-action:none;cursor:pointer}
.key:focus-visible,canvas:focus-visible{outline:2px solid #87d4bf;outline-offset:-2px}
.brand{display:none}
.calculator.skin-mode{position:relative;width:min(100vw,calc(100vh * var(--skin-ratio)));aspect-ratio:var(--skin-ratio);flex-shrink:0;padding:0;border:0;border-radius:0;background:var(--normal-image) center/100% 100% no-repeat;box-shadow:none}
.skin-mode .screen-frame{position:absolute;padding:0;border-radius:0;box-shadow:none}
.skin-mode .screen-frame canvas{width:100%;height:100%}
.skin-mode .brand{display:none}.skin-mode .keypad{display:contents}
.skin-mode .key{position:absolute;min-height:0;min-width:0;border:0;border-radius:0;padding:0;background-color:transparent;background-image:none;box-shadow:none;transform:none;color:transparent}
.skin-mode .key:hover{background-image:var(--hover-image)}
.skin-mode .key.pressed,.skin-mode .key:active{background-image:var(--pressed-image);transform:none;box-shadow:none}
.skin-mode .key:focus-visible{outline-offset:-2px}
</style>
<main><section class="calculator" aria-label="HP Prime emulator"><div class="screen-frame"><canvas id="screen" width="320" height="240" tabindex="0" aria-label="Calculator touchscreen"></canvas></div><div class="brand"><span>LEFONY</span><span>PRIME G2</span></div><div class="keypad" aria-label="HP Prime keypad">__KEYS__</div></section>
</main>
<script>
'use strict';
const screen=document.querySelector('#screen'),ctx=screen.getContext('2d');
let connection='Connecting…';
const skins=__SKINS__,held=new Map(),touches=new Map();
let buttons=[...document.querySelectorAll('[data-key]')],activeSkin=null;
let stopped=false,queue=Promise.resolve(),pendingMoves=false,pendingInputs=0;
const names=()=>[...new Set(held.values())];
function state(){return {keys:names(),touch:[...touches.values()].map(v=>v.contact)}}
function paintKeys(){const active=new Set(names());buttons.forEach(b=>b.classList.toggle('pressed',active.has(b.dataset.key)))}
function post(action,value){return fetch(action,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(value),signal:AbortSignal.timeout(4000)}).then(r=>{if(!r.ok)throw Error('Emulator connection ended')})}
function send(){if(stopped)return;if(pendingInputs>=32){fail();return}const value=state();paintKeys();pendingInputs++;queue=queue.then(()=>stopped?null:post('input',value)).catch(fail).finally(()=>pendingInputs--)}
function fail(){if(stopped)return;stopped=true;held.clear();touches.clear();paintKeys();connection='Disconnected. Restart the run from your terminal.'}
function release(){held.clear();touches.clear();send()}
function point(event,id){const r=screen.getBoundingClientRect();return [id,Math.max(0,Math.min(319,Math.floor((event.clientX-r.left)*320/r.width))),Math.max(0,Math.min(239,Math.floor((event.clientY-r.top)*240/r.height)))]}
function bindKey(b){
 b.addEventListener('pointerdown',e=>{if(e.button!==0)return;e.preventDefault();b.setPointerCapture(e.pointerId);held.set('p'+e.pointerId,b.dataset.key);send()});
 const up=e=>{if(held.delete('p'+e.pointerId))send()};b.addEventListener('pointerup',up);b.addEventListener('pointercancel',up);b.addEventListener('lostpointercapture',up);
 // Keyboard/assistive activation of a focused keypad button.
 b.addEventListener('click',e=>{if(e.detail!==0)return;held.set('activate',b.dataset.key);send();held.delete('activate');send()});
}
buttons.forEach(bindKey);
screen.addEventListener('pointerdown',e=>{if(e.button!==0||touches.size===2)return;e.preventDefault();screen.focus();screen.setPointerCapture(e.pointerId);const used=new Set([...touches.values()].map(v=>v.contact[0]));const id=used.has(0)?1:0;touches.set(e.pointerId,{contact:point(e,id)});send()});
screen.addEventListener('pointermove',e=>{const v=touches.get(e.pointerId);if(!v)return;v.contact=point(e,v.contact[0]);if(!pendingMoves){pendingMoves=true;setTimeout(()=>{pendingMoves=false;send()},40)}});
const touchUp=e=>{if(touches.delete(e.pointerId))send()};screen.addEventListener('pointerup',touchUp);screen.addEventListener('pointercancel',touchUp);screen.addEventListener('lostpointercapture',touchUp);
const shortcuts={ArrowUp:'up',ArrowDown:'down',ArrowLeft:'left',ArrowRight:'right',Enter:'ok',Escape:'back',Backspace:'backspace',Home:'home',Shift:'shift',Alt:'alpha',' ':'space','0':'zero','1':'one','2':'two','3':'three','4':'four','5':'five','6':'six','7':'seven','8':'eight','9':'nine','+':'plus','-':'minus','*':'multiply','/':'divide','.':'dot',',':'comma','(':'parenthesis',F1:'symb',F2:'plot',F3:'num',F4:'help',F5:'view',F6:'menu'};
window.addEventListener('keydown',e=>{if(e.metaKey||e.ctrlKey||e.target.closest('select,button,summary'))return;const name=shortcuts[e.key];if(!name)return;e.preventDefault();if(e.repeat)return;held.set('k'+e.code,name);send()});
window.addEventListener('keyup',e=>{if(held.delete('k'+e.code)){e.preventDefault();send()}});
window.addEventListener('blur',release);document.addEventListener('visibilitychange',()=>{if(document.hidden)release()});
window.addEventListener('pagehide',()=>{held.clear();touches.clear();fetch('input',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(state()),keepalive:true}).catch(()=>{})});
setInterval(()=>{if(!stopped&&(held.size||touches.size))send()},350);
const calculator=document.querySelector('.calculator');
function rect(element,r,skin){Object.assign(element.style,{left:(r.x/skin.width*100)+'%',top:(r.y/skin.height*100)+'%',width:(r.width/skin.width*100)+'%',height:(r.height/skin.height*100)+'%'})}
function chooseSkin(skin){
 release();activeSkin=skin;calculator.classList.add('skin-mode');
 calculator.style.setProperty('--skin-ratio',skin.width+'/'+skin.height);
 for(const state of ['normal','hover','pressed'])calculator.style.setProperty('--'+state+'-image','url("'+skin.images[state]+'")');
 rect(document.querySelector('.screen-frame'),skin.screen,skin);
 const keypad=document.querySelector('.keypad');keypad.replaceChildren();
 buttons=skin.keys.map(k=>{const b=document.createElement('button');b.type='button';b.className='key';b.dataset.key=k.name;b.setAttribute('aria-label',k.name==='onoff'?'On / Off':k.label);b.title=b.getAttribute('aria-label');rect(b,k,skin);
 b.style.backgroundSize=(skin.width/k.width*100)+'% '+(skin.height/k.height*100)+'%';
 b.style.backgroundPosition=(k.x/(skin.width-k.width)*100)+'% '+(k.y/(skin.height-k.height)*100)+'%';
 bindKey(b);keypad.append(b);return b});screen.focus();
}
if(skins.length)chooseSkin(skins.find(s=>s.title==='Medium')||skins[0]);
// Narrow interface used only by the native desktop host's application menus.
window.lefonyDesktop={
 configuration:()=>({skins:skins.map(({id,title,width,height})=>({id,title,width,height})),activeSkin:activeSkin?.id}),
 chooseSkin:id=>{const skin=skins.find(s=>s.id===id);if(skin)chooseSkin(skin)},
 release,
 connection:()=>connection
};
async function frame(){if(stopped)return;try{const r=await fetch('frame',{signal:AbortSignal.timeout(4000)});if(!r.ok)throw Error();const bitmap=await createImageBitmap(await r.blob());if(!stopped){ctx.drawImage(bitmap,0,0);connection='Connected'}bitmap.close();}catch{fail()}if(!stopped)setTimeout(frame,100)}
frame();screen.focus();
</script></html>'''
