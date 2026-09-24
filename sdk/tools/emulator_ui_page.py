# SPDX-License-Identifier: GPL-3.0-or-later
"""Self-contained browser UI; no remote assets or calculator data uploads."""
from html import escape

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


def page(title):
    rows = []
    for index, row in enumerate(ROWS):
        rows.append(f'<div class="key-row cols-{len(row)}">' + ''.join(key(*item) for item in row) + '</div>')
        if index == 1:
            rows.append('<div class="arrows" aria-label="Direction keys">' + ''.join(key(*item) for item in [('up', '↑'), ('left', '←'), ('down', '↓'), ('right', '→')]) + '</div>')
    return HTML.replace('__TITLE__', escape(title)).replace('__KEYS__', '\n'.join(rows))


HTML = r'''<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Lefony Emulator · __TITLE__</title>
<style>
:root{color-scheme:dark;font:14px system-ui,sans-serif;background:#10171c;color:#edf1ef}
*{box-sizing:border-box}body{margin:0}header{max-width:1100px;margin:auto;padding:18px 24px;display:flex;align-items:center;justify-content:space-between;gap:20px}
h1{font-size:18px;margin:0 0 3px;font-weight:650}.subtitle{color:#a0b2b7;font-size:12px}
button,select{font:inherit;color:inherit;background:#28343b;border:1px solid #4b5b63;border-radius:7px;padding:8px 12px;cursor:pointer}
button:focus-visible,select:focus-visible,canvas:focus-visible{outline:3px solid #87d4bf;outline-offset:3px}
.toolbar{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.toolbar label{color:#b7c8ca}#stop{background:#403034;border-color:#735357}
main{max-width:1100px;margin:0 auto;padding:0 20px 30px;display:flex;flex-direction:column;align-items:center}
.calculator{--screen-width:640px;width:min(100%,calc(var(--screen-width) + 46px));padding:14px;background:linear-gradient(145deg,#39464c,#212c32);border:1px solid #5b6b72;border-radius:18px;box-shadow:0 18px 60px #0005}
.screen-frame{background:#0a0f11;padding:8px;border-radius:8px;box-shadow:inset 0 2px 5px #000}
canvas{width:100%;height:auto;aspect-ratio:4/3;display:block;background:#fff;image-rendering:pixelated;touch-action:none;cursor:crosshair}
.brand{font-size:10px;letter-spacing:2px;color:#c7d6d8;display:flex;justify-content:space-between;margin:10px 3px}
.keypad{display:grid;gap:6px}.key-row{display:grid;gap:7px}.cols-6{grid-template-columns:repeat(6,1fr)}.cols-5{grid-template-columns:repeat(5,1fr)}.cols-3{grid-template-columns:1fr 1fr 3fr}
.key{min-width:0;min-height:35px;box-shadow:0 3px 0 #0b1116;user-select:none;touch-action:none;padding:5px 3px;background:linear-gradient(#48565e,#35434b);font-size:15px}
.key-row:nth-child(-n+2) .key{font-size:12px;min-height:30px;background:#222e35}
.key.pressed,.key:active{background:#547d73;box-shadow:0 1px 0 #0b1116;transform:translateY(2px)}
.key.shift{color:#a9d0ff}.key.alpha{color:#f6c492}.key.ok{background:#598775;color:#fff;font-weight:650}.key.back{color:#f2b8af}
.arrows{display:grid;grid-template-columns:repeat(3,48px);grid-template-rows:28px 28px;gap:5px;justify-content:center;margin:2px 0 5px}.arrows .key{min-height:28px;padding:0}.up{grid-column:2}.left{grid-column:1;grid-row:2}.down{grid-column:2;grid-row:2}.right{grid-column:3;grid-row:2}
.hint{max-width:640px;font-size:12px;line-height:1.6;color:#aec0c4;margin:14px 2px 0}#status{color:#98d9ba}details{max-width:640px;width:100%;margin-top:12px;color:#b9c9cc;font-size:12px}summary{cursor:pointer}details p{line-height:1.7}
@media(max-width:600px){header{padding:12px;align-items:flex-start}main{padding:0 8px 20px}.calculator{padding:9px}.toolbar{justify-content:flex-end}h1{font-size:15px}.key{min-height:36px;font-size:13px}}
</style>
<header><div><h1>Lefony Emulator</h1><div class="subtitle">__TITLE__ · HP Prime G2</div></div><div class="toolbar"><label for="zoom">Screen</label><select id="zoom"><option value="480">1.5×</option><option value="640" selected>2×</option><option value="960">3×</option></select><button id="stop">Stop emulator</button></div></header>
<main><section class="calculator" aria-label="HP Prime emulator"><div class="screen-frame"><canvas id="screen" width="320" height="240" tabindex="0" aria-label="Calculator touchscreen"></canvas></div><div class="brand"><span>LEFONY</span><span>PRIME G2</span></div><div class="keypad" aria-label="HP Prime keypad">__KEYS__</div></section>
<p class="hint"><span id="status" role="status">Connecting…</span><br>Click the screen to touch it. Use the keypad below or your keyboard’s arrows, numbers and Enter. Shift and Alpha work like calculator keys.</p>
<details><summary>Keyboard shortcuts &amp; saving</summary><p>Enter = Enter · Escape = Esc · Backspace = ⌫ · Arrow keys = directions · Home = Home · F1–F6 = Symb, Plot, Num, Help, View, Menu. Use the calculator’s Alpha key for letters. Physical Shift = Shift; Alt = Alpha. Browser shortcuts with Command or Control remain available.</p><p>Save inside the app, then use <b>Stop emulator</b> to close normally. Closing this tab releases all keys; reopen the same local address to reconnect. A named workspace keeps its saved calculator data between runs.</p></details></main>
<script>
'use strict';
const screen=document.querySelector('#screen'),ctx=screen.getContext('2d'),status=document.querySelector('#status');
const buttons=[...document.querySelectorAll('[data-key]')],held=new Map(),touches=new Map();
let stopped=false,queue=Promise.resolve(),pendingMoves=false,pendingInputs=0;
const names=()=>[...new Set(held.values())];
function state(){return {keys:names(),touch:[...touches.values()].map(v=>v.contact)}}
function paintKeys(){const active=new Set(names());buttons.forEach(b=>b.classList.toggle('pressed',active.has(b.dataset.key)))}
function post(action,value){return fetch(action,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(value),signal:AbortSignal.timeout(4000)}).then(r=>{if(!r.ok)throw Error('Emulator connection ended')})}
function send(){if(stopped)return;if(pendingInputs>=32){fail();return}const value=state();paintKeys();pendingInputs++;queue=queue.then(()=>stopped?null:post('input',value)).catch(fail).finally(()=>pendingInputs--)}
function fail(){if(stopped)return;stopped=true;held.clear();touches.clear();paintKeys();status.textContent='Disconnected. Restart the run from your terminal.'}
function release(){held.clear();touches.clear();send()}
function point(event,id){const r=screen.getBoundingClientRect();return [id,Math.max(0,Math.min(319,Math.floor((event.clientX-r.left)*320/r.width))),Math.max(0,Math.min(239,Math.floor((event.clientY-r.top)*240/r.height)))]}
buttons.forEach(b=>{
 b.addEventListener('pointerdown',e=>{if(e.button!==0)return;e.preventDefault();b.setPointerCapture(e.pointerId);held.set('p'+e.pointerId,b.dataset.key);send()});
 const up=e=>{if(held.delete('p'+e.pointerId))send()};b.addEventListener('pointerup',up);b.addEventListener('pointercancel',up);b.addEventListener('lostpointercapture',up);
 // Keyboard/assistive activation of a focused keypad button.
 b.addEventListener('click',e=>{if(e.detail!==0)return;held.set('activate',b.dataset.key);send();held.delete('activate');send()});
});
screen.addEventListener('pointerdown',e=>{if(e.button!==0||touches.size===2)return;e.preventDefault();screen.focus();screen.setPointerCapture(e.pointerId);const used=new Set([...touches.values()].map(v=>v.contact[0]));const id=used.has(0)?1:0;touches.set(e.pointerId,{contact:point(e,id)});send()});
screen.addEventListener('pointermove',e=>{const v=touches.get(e.pointerId);if(!v)return;v.contact=point(e,v.contact[0]);if(!pendingMoves){pendingMoves=true;setTimeout(()=>{pendingMoves=false;send()},40)}});
const touchUp=e=>{if(touches.delete(e.pointerId))send()};screen.addEventListener('pointerup',touchUp);screen.addEventListener('pointercancel',touchUp);screen.addEventListener('lostpointercapture',touchUp);
const shortcuts={ArrowUp:'up',ArrowDown:'down',ArrowLeft:'left',ArrowRight:'right',Enter:'ok',Escape:'back',Backspace:'backspace',Home:'home',Shift:'shift',Alt:'alpha',' ':'space','0':'zero','1':'one','2':'two','3':'three','4':'four','5':'five','6':'six','7':'seven','8':'eight','9':'nine','+':'plus','-':'minus','*':'multiply','/':'divide','.':'dot',',':'comma','(':'parenthesis',F1:'symb',F2:'plot',F3:'num',F4:'help',F5:'view',F6:'menu'};
window.addEventListener('keydown',e=>{if(e.metaKey||e.ctrlKey||e.target.closest('select,button,summary'))return;const name=shortcuts[e.key];if(!name)return;e.preventDefault();if(e.repeat)return;held.set('k'+e.code,name);send()});
window.addEventListener('keyup',e=>{if(held.delete('k'+e.code)){e.preventDefault();send()}});
window.addEventListener('blur',release);document.addEventListener('visibilitychange',()=>{if(document.hidden)release()});
window.addEventListener('pagehide',()=>{held.clear();touches.clear();fetch('input',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(state()),keepalive:true}).catch(()=>{})});
setInterval(()=>{if(!stopped&&(held.size||touches.size))send()},350);
document.querySelector('#zoom').addEventListener('change',e=>{document.querySelector('.calculator').style.setProperty('--screen-width',e.target.value+'px');screen.focus()});
document.querySelector('#stop').addEventListener('click',async()=>{release();await queue;try{await post('stop',{});stopped=true;status.textContent='Emulator stopped. You can close this tab.'}catch{fail()}});
async function frame(){if(stopped)return;try{const r=await fetch('frame',{signal:AbortSignal.timeout(4000)});if(!r.ok)throw Error();const bitmap=await createImageBitmap(await r.blob());ctx.drawImage(bitmap,0,0);bitmap.close();status.textContent='Connected';}catch{fail()}if(!stopped)setTimeout(frame,100)}
frame();screen.focus();
</script></html>'''
