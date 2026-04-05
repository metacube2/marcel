#!/usr/bin/env python3
"""
VU1 Meter Web GUI v3
====================
Skeuomorphes VU-Meter mit echter Galvanometer-Physik,
Audio-Passthrough und Physik-Visualisierung.
Öffne http://localhost:8080 im Browser.
"""

import requests, time, argparse, numpy as np, sys, math
import threading, json, psutil
from flask import Flask, render_template_string, jsonify, request as flask_request

try:
    import sounddevice as sd
except ImportError:
    print("❌ sounddevice nicht installiert!")
    sys.exit(1)

app = Flask(__name__)

# ── Globals ───────────────────────────────────────────────────
meter = None
client = None
dial_uid = None
cpu_dial_uid = None
disk_dial_uid = None
running = False
current_level = 0
current_peak = 0

# ══════════════════════════════════════════════════════════════
# HTML / CSS / JS — Skeuomorphes VU-Meter
# ══════════════════════════════════════════════════════════════

HTML_PAGE = r"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>VU1 Meter</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=JetBrains+Mono:wght@400;700&family=DM+Sans:wght@300;400;500;700&display=swap');

:root {
  --wood: #3a2518;
  --wood-light: #5c3a28;
  --wood-grain: #4a3020;
  --cream: #f5e6c8;
  --cream-dark: #d4c4a0;
  --needle-red: #c0392b;
  --brass: #b8860b;
  --brass-light: #d4a017;
  --glass-shine: rgba(255,255,255,0.08);
  --led-green: #39ff14;
  --led-red: #ff1744;
  --led-amber: #ffab00;
  --led-off: #1a1a1a;
  --panel-bg: #1a1512;
  --panel-border: #2a2018;
}

* { margin:0; padding:0; box-sizing:border-box; }

body {
  font-family: 'DM Sans', sans-serif;
  background: var(--panel-bg);
  color: #ccc;
  min-height: 100vh;
  display: flex;
  justify-content: center;
  padding: 16px;
}

.app { max-width: 560px; width: 100%; }

/* ── VU Meter Face ────────────────────────────── */
.vu-housing {
  background: linear-gradient(145deg, var(--wood) 0%, var(--wood-light) 40%, var(--wood-grain) 100%);
  border-radius: 16px;
  padding: 20px;
  box-shadow:
    0 8px 32px rgba(0,0,0,0.6),
    inset 0 1px 0 rgba(255,255,255,0.05),
    0 0 0 1px rgba(255,255,255,0.03);
  position: relative;
}
.vu-housing::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0; bottom: 0;
  border-radius: 16px;
  background: repeating-linear-gradient(
    90deg, transparent, transparent 3px,
    rgba(0,0,0,0.03) 3px, rgba(0,0,0,0.03) 6px
  );
  pointer-events: none;
}

.vu-face {
  background: linear-gradient(180deg, var(--cream) 0%, var(--cream-dark) 100%);
  border-radius: 12px;
  padding: 0;
  position: relative;
  overflow: hidden;
  height: 240px;
  box-shadow:
    inset 0 2px 8px rgba(0,0,0,0.15),
    0 1px 0 rgba(255,255,255,0.1);
}

/* Glass reflection */
.vu-face::after {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 50%;
  background: linear-gradient(180deg, rgba(255,255,255,0.12) 0%, transparent 100%);
  border-radius: 12px 12px 0 0;
  pointer-events: none;
  z-index: 10;
}

.vu-canvas { width: 100%; height: 100%; display: block; }

/* Brass screws */
.screw {
  position: absolute;
  width: 12px; height: 12px;
  border-radius: 50%;
  background: radial-gradient(circle at 35% 35%, var(--brass-light), var(--brass) 60%, #8B6914);
  box-shadow: 0 1px 3px rgba(0,0,0,0.4), inset 0 0 2px rgba(255,255,255,0.3);
}
.screw::after {
  content: '';
  position: absolute;
  top: 4px; left: 2px; right: 2px; height: 1px;
  background: rgba(0,0,0,0.3);
  transform: rotate(-30deg);
}
.screw-tl { top: 6px; left: 6px; }
.screw-tr { top: 6px; right: 6px; }
.screw-bl { bottom: 6px; left: 6px; }
.screw-br { bottom: 6px; right: 6px; }

/* ── Level readout ────────────────────────────── */
.readout-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 4px 6px;
}
.readout {
  font-family: 'JetBrains Mono', monospace;
  font-size: 1.8em;
  font-weight: 700;
  color: var(--cream);
  text-shadow: 0 0 12px rgba(245,230,200,0.3);
}
.readout-sub {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.82em;
  color: #666;
}
.readout-peak { color: var(--needle-red); }

/* ── LED bar meter ────────────────────────────── */
.led-bar {
  display: flex;
  gap: 2px;
  height: 10px;
  margin: 4px 0 12px;
  padding: 3px 4px;
  background: #0a0a08;
  border-radius: 4px;
  border: 1px solid #222;
}
.led-seg {
  flex: 1;
  border-radius: 1px;
  background: var(--led-off);
  transition: background 0.04s;
}

/* ── Controls panel ───────────────────────────── */
.ctrl-panel {
  background: linear-gradient(180deg, #1e1a15 0%, #151210 100%);
  border-radius: 10px;
  margin-top: 12px;
  padding: 14px;
  border: 1px solid var(--panel-border);
}
.ctrl-title {
  font-size: 0.68em;
  color: #555;
  text-transform: uppercase;
  letter-spacing: 0.14em;
  margin-bottom: 10px;
}

/* Selects */
.sel-group { margin-bottom: 10px; }
.sel-group label {
  display: block;
  font-size: 0.72em;
  color: #555;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin-bottom: 4px;
}
.sel-group select {
  width: 100%;
  padding: 7px 8px;
  background: #0e0c0a;
  color: #aaa;
  border: 1px solid #2a2520;
  border-radius: 5px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.78em;
}

/* Mode + monitor buttons */
.btn-row { display: flex; gap: 6px; margin: 10px 0; flex-wrap: wrap; }
.btn-sm {
  padding: 6px 12px;
  font-size: 0.76em;
  font-family: 'DM Sans', sans-serif;
  font-weight: 500;
  background: transparent;
  border: 1px solid #2a2520;
  color: #777;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.12s;
}
.btn-sm:hover { border-color: var(--brass); color: var(--brass); }
.btn-sm.active { border-color: var(--brass-light); color: var(--brass-light); background: rgba(184,134,11,0.08); }
.btn-sm.monitor-on { border-color: var(--led-green); color: var(--led-green); background: rgba(57,255,20,0.06); }
.btn-sm.solo-lo { border-color: #4fc3f7; color: #4fc3f7; background: rgba(79,195,247,0.06); }
.btn-sm.solo-hi { border-color: #ff8a65; color: #ff8a65; background: rgba(255,138,101,0.06); }

/* Sliders */
.slider-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 0;
}
.slider-row label {
  flex: 0 0 100px;
  font-size: 0.78em;
  color: #666;
}
.slider-row input[type=range] {
  flex: 1;
  height: 3px;
  border-radius: 2px;
  background: #222;
  outline: none;
  -webkit-appearance: none;
}
.slider-row input[type=range]::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 14px; height: 14px;
  border-radius: 50%;
  background: var(--brass);
  cursor: pointer;
  border: 2px solid #0e0c0a;
}
.slider-val {
  flex: 0 0 48px;
  text-align: right;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.78em;
  color: var(--brass-light);
  font-weight: 700;
}

/* Action buttons */
.action-row { display: flex; gap: 8px; margin: 12px 0 6px; }
.btn-action {
  flex: 1;
  padding: 12px;
  font-family: 'DM Sans', sans-serif;
  font-size: 0.9em;
  font-weight: 700;
  letter-spacing: 0.06em;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  transition: transform 0.06s;
}
.btn-action:active { transform: scale(0.97); }
.btn-start { background: #2e4a1e; color: #a0d468; }
.btn-start.running { background: #5a1a1a; color: #f5a0a0; }
.btn-reset { background: #1a1816; color: #666; border: 1px solid #2a2520; }

/* Physics viz */
.physics-viz {
  background: #0a0908;
  border-radius: 8px;
  border: 1px solid #1e1a15;
  overflow: hidden;
  margin-top: 10px;
  min-height: 120px;
}
.physics-canvas { width: 100%; height: 120px; display: block; min-height: 120px; }

/* IEC info */
.iec-box {
  background: rgba(57,255,20,0.03);
  border: 1px solid rgba(57,255,20,0.1);
  border-radius: 6px;
  padding: 10px 12px;
  margin-top: 8px;
  font-size: 0.78em;
  color: #6a6;
  line-height: 1.6;
}
.iec-box b { color: #8c8; }

/* Dual-band controls */
.dualband-box {
  background: rgba(79,195,247,0.03);
  border: 1px solid rgba(79,195,247,0.08);
  border-radius: 6px;
  padding: 10px 12px;
  margin-top: 8px;
}
.db-readout-band {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75em;
  color: #555;
  text-align: center;
  margin-top: 6px;
}

/* Extra dials */
.extras {
  margin-top: 14px;
  border-top: 1px solid #1e1a15;
  padding-top: 12px;
}
.extra-card {
  background: #131110;
  border-radius: 6px;
  padding: 8px 10px;
  margin-bottom: 5px;
  border: 1px solid #1e1a15;
}

.status-line {
  text-align: center;
  font-size: 0.72em;
  color: #444;
  font-family: 'JetBrains Mono', monospace;
  margin-top: 6px;
}
</style>
</head>
<body>
<div class="app">

  <!-- VU Meter Face -->
  <div class="vu-housing">
    <div class="screw screw-tl"></div>
    <div class="screw screw-tr"></div>
    <div class="screw screw-bl"></div>
    <div class="screw screw-br"></div>
    <div class="vu-face">
      <canvas class="vu-canvas" id="vu-canvas"></canvas>
    </div>
  </div>

  <!-- Readout -->
  <div class="readout-bar">
    <div class="readout" id="readout">0%</div>
    <div>
      <span class="readout-sub">pk </span>
      <span class="readout-sub readout-peak" id="peak-val">0%</span>
    </div>
    <div class="readout-sub" id="db-val">— dB</div>
  </div>

  <!-- LED Bar -->
  <div class="led-bar" id="led-bar"></div>

  <!-- Controls -->
  <div class="ctrl-panel">
    <div class="ctrl-title">Audio</div>
    <div class="sel-group">
      <label>Eingang</label>
      <select id="dev-in" onchange="setDevice('in', this.value)"><option>Lade…</option></select>
    </div>
    <div class="sel-group">
      <label>Ausgang (Monitor)</label>
      <select id="dev-out" onchange="setDevice('out', this.value)"><option>Lade…</option></select>
    </div>

    <div class="btn-row">
      <button class="btn-sm" id="btn-monitor" onclick="toggleMonitor()">🔇 Monitor</button>
      <button class="btn-sm" id="btn-bypass" onclick="toggleBypass()">Bypass</button>
      <button class="btn-sm" id="btn-solo-lo" onclick="toggleSolo('lo')">Solo Lo</button>
      <button class="btn-sm" id="btn-solo-hi" onclick="toggleSolo('hi')">Solo Hi</button>
    </div>

    <div class="ctrl-title" style="margin-top:14px">Modus</div>
    <div class="btn-row">
      <button class="btn-sm active" id="mode-full" onclick="setMode('full')">Breitband</button>
      <button class="btn-sm" id="mode-dual" onclick="setMode('dualband')">Dual-Band</button>
      <button class="btn-sm" id="mode-iec" onclick="setMode('iec_true')">IEC True</button>
      <button class="btn-sm" id="mode-natural" onclick="setMode('natural_formula')">Natural+</button>
    </div>

    <!-- Presets -->
    <div class="btn-row">
      <button class="btn-sm" onclick="preset('iec_vu')">IEC VU</button>
      <button class="btn-sm" onclick="preset('bbc_ppm')">BBC PPM</button>
      <button class="btn-sm" onclick="preset('natural_vu')">Natural VU</button>
      <button class="btn-sm" onclick="preset('bouncy')">Bouncy</button>
      <button class="btn-sm" onclick="preset('heavy')">Heavy</button>
      <button class="btn-sm" onclick="preset('fast')">Fast</button>
      <button class="btn-sm" onclick="preset('analog')">Analog</button>
    </div>

    <!-- Dual-Band controls -->
    <div class="dualband-box" id="dualband-box" style="display:none">
      <div class="slider-row">
        <label>Crossover Hz</label>
        <input type="range" id="crossover" min="80" max="1000" step="10" value="250" oninput="updSlider('crossover',this.value)">
        <span class="slider-val" id="crossover-val">250</span>
      </div>
      <div class="slider-row">
        <label>Low Gewicht</label>
        <input type="range" id="lo_weight" min="0" max="1" step="0.05" value="0.6" oninput="updDualW('lo',this.value)">
        <span class="slider-val" id="lo_weight-val">0.60</span>
      </div>
      <div class="slider-row">
        <label>High Gewicht</label>
        <input type="range" id="hi_weight" min="0" max="1" step="0.05" value="0.4" oninput="updDualW('hi',this.value)">
        <span class="slider-val" id="hi_weight-val">0.40</span>
      </div>
      <div class="db-readout-band" id="db-bands">— dB lo · — dB hi</div>
    </div>

    <!-- IEC info -->
    <div class="iec-box" id="iec-box" style="display:none">
      <b>IEC True Ballistics</b> — Lobdell-Modell<br>
      |x| → Biquad LPF 2.224 Hz, Q 0.6053<br>
      300ms Anstiegszeit, ~1% Überschwingen<br>
      <span style="color:#555">Der Filter <i>ist</i> die Nadelphysik (+ kurzer Transient-Assist).</span>
    </div>
    <div class="iec-box" id="natural-box" style="display:none">
      <b>Natural+</b> — neue Ballistikformel<br>
      Hüllkurve mit separatem Attack/Release + 2.-Ordnung Nadelmodell<br>
      Natürliches Einschwingen, weniger Zappeln, weicher Rücklauf.
    </div>

    <!-- Physics sliders -->
    <div id="physics-ctrls">
      <div class="ctrl-title" style="margin-top:14px">Physik</div>
      <div class="slider-row">
        <label>Masse</label>
        <input type="range" id="mass" min="0.05" max="4" step="0.05" value="0.8" oninput="updSlider('mass',this.value)">
        <span class="slider-val" id="mass-val">0.80</span>
      </div>
      <div class="slider-row">
        <label>Dämpfung</label>
        <input type="range" id="damping" min="0" max="4" step="0.05" value="1.2" oninput="updSlider('damping',this.value)">
        <span class="slider-val" id="damping-val">1.20</span>
      </div>
      <div class="slider-row">
        <label>Feder</label>
        <input type="range" id="spring" min="0.1" max="20" step="0.1" value="3.0" oninput="updSlider('spring',this.value)">
        <span class="slider-val" id="spring-val">3.00</span>
      </div>
      <div class="slider-row">
        <label>Schwerkraft</label>
        <input type="range" id="gravity" min="-5" max="5" step="0.1" value="0" oninput="updSlider('gravity',this.value)">
        <span class="slider-val" id="gravity-val">0.00</span>
      </div>
      <div class="slider-row">
        <label>Empfind. dB</label>
        <input type="range" id="sensitivity" min="-60" max="-10" step="1" value="-40" oninput="updSlider('sensitivity',this.value)">
        <span class="slider-val" id="sensitivity-val">-40</span>
      </div>
    </div>

    <!-- Physics Visualization -->
    <div class="physics-viz" id="physics-viz">
      <canvas class="physics-canvas" id="phys-canvas"></canvas>
    </div>

    <!-- Buttons -->
    <div class="action-row">
      <button class="btn-action btn-start" id="btn-start" onclick="toggleStart()">▶ START</button>
      <button class="btn-action btn-reset" onclick="resetAll()">↺ RESET</button>
    </div>
    <div class="status-line" id="status">bereit</div>

    <!-- Extra dials -->
    <div class="extras">
      <div class="ctrl-title">Weitere Dials</div>
      <div id="extra-dials"></div>
    </div>
  </div>
</div>

<script>
// ── State ──
let isRunning = false;
let monitorOn = false;
let bypassOn = false;
let soloMode = 'off'; // 'off','lo','hi'
let physData = {pos:0, vel:0, target:0, peak:0, f_spring:0, f_damping:0, f_gravity:0};

// ── Init LED bar ──
const ledBar = document.getElementById('led-bar');
for(let i=0; i<40; i++){
  const s = document.createElement('div');
  s.className = 'led-seg';
  ledBar.appendChild(s);
}
const ledSegs = ledBar.querySelectorAll('.led-seg');

// ── Load devices ──
fetch('/devices').then(r=>r.json()).then(d=>{
  const selIn=document.getElementById('dev-in');
  const selOut=document.getElementById('dev-out');
  selIn.innerHTML=d.inputs.map(x=>`<option value="${x.id}">${x.id}: ${x.name}</option>`).join('');
  selOut.innerHTML='<option value="-1">— Aus —</option>'+
    d.outputs.map(x=>`<option value="${x.id}">${x.id}: ${x.name}</option>`).join('');
  fetch('/current_device').then(r=>r.json()).then(c=>{
    selIn.value=c.input;
    selOut.value=c.output;
  });
});

function setDevice(which, id){
  fetch('/set_device/'+which+'/'+id);
}

// ── Monitor / Bypass / Solo ──
function toggleMonitor(){
  monitorOn=!monitorOn;
  fetch('/set/monitor/'+(monitorOn?'1':'0'));
  const b=document.getElementById('btn-monitor');
  b.textContent=monitorOn?'🔊 Monitor':'🔇 Monitor';
  b.classList.toggle('monitor-on', monitorOn);
}
function toggleBypass(){
  bypassOn=!bypassOn;
  fetch('/set/bypass/'+(bypassOn?'1':'0'));
  const b=document.getElementById('btn-bypass');
  b.classList.toggle('active', bypassOn);
}
function toggleSolo(band){
  if(soloMode===band) soloMode='off';
  else soloMode=band;
  fetch('/set/solo/'+soloMode);
  document.getElementById('btn-solo-lo').classList.toggle('solo-lo', soloMode==='lo');
  document.getElementById('btn-solo-hi').classList.toggle('solo-hi', soloMode==='hi');
}

// ── Mode ──
function setMode(mode){
  fetch('/set/mode/'+mode);
  document.getElementById('dualband-box').style.display=mode==='dualband'?'block':'none';
  document.getElementById('iec-box').style.display=mode==='iec_true'?'block':'none';
  document.getElementById('natural-box').style.display=mode==='natural_formula'?'block':'none';
  document.getElementById('physics-ctrls').style.display=(mode==='iec_true'||mode==='natural_formula')?'none':'block';
  ['full','dual','iec','natural'].forEach(m=>{
    const btn=document.getElementById('mode-'+m);
    const act=(m==='full'&&mode==='full')||(m==='dual'&&mode==='dualband')||(m==='iec'&&mode==='iec_true')||(m==='natural'&&mode==='natural_formula');
    btn.classList.toggle('active', act);
  });
}

// ── Sliders ──
function updSlider(name, val){
  const el=document.getElementById(name+'-val');
  el.textContent=name==='sensitivity'||name==='crossover'?parseInt(val):parseFloat(val).toFixed(2);
  fetch('/set/'+name+'/'+val);
}
function updDualW(band, val){
  const other=band==='lo'?'hi':'lo';
  const ov=Math.max(0,Math.min(1,1-parseFloat(val)));
  document.getElementById(band+'_weight-val').textContent=parseFloat(val).toFixed(2);
  document.getElementById(other+'_weight-val').textContent=ov.toFixed(2);
  document.getElementById(other+'_weight').value=ov;
  fetch('/set/'+band+'_weight/'+val);
  fetch('/set/'+other+'_weight/'+ov);
}

// ── Presets ──
function preset(name){
  const P={
    iec_vu:{mass:1.0,damping:1.5,spring:4.0,gravity:0},
    bbc_ppm:{mass:0.3,damping:2.0,spring:12.0,gravity:0},
    natural_vu:{mass:1.35,damping:2.6,spring:6.4,gravity:0.1},
    bouncy:{mass:0.6,damping:0.4,spring:6.0,gravity:0},
    heavy:{mass:3.0,damping:2.5,spring:2.0,gravity:1.0},
    fast:{mass:0.1,damping:1.8,spring:15.0,gravity:0},
    analog:{mass:0.8,damping:1.2,spring:5.0,gravity:0.2}
  };
  const p=P[name]; if(!p) return;
  Object.entries(p).forEach(([k,v])=>{
    document.getElementById(k).value=v;
    document.getElementById(k+'-val').textContent=parseFloat(v).toFixed(2);
    fetch('/set/'+k+'/'+v);
  });
}

// ── Start/Stop ──
function toggleStart(){
  fetch('/toggle').then(r=>r.json()).then(d=>{
    if(d.error){document.getElementById('status').textContent='⚠ '+d.error; return;}
    isRunning=d.running;
    const b=document.getElementById('btn-start');
    b.textContent=isRunning?'⏹ STOP':'▶ START';
    b.classList.toggle('running', isRunning);
    document.getElementById('status').textContent=isRunning?'läuft':'gestoppt';
    if(isRunning) pollLevel();
  });
}
function resetAll(){
  fetch('/reset').then(()=>{
    const defs={mass:0.8,damping:1.2,spring:3.0,gravity:0,sensitivity:-40};
    Object.entries(defs).forEach(([k,v])=>{
      document.getElementById(k).value=v;
      document.getElementById(k+'-val').textContent=k==='sensitivity'?v:parseFloat(v).toFixed(2);
    });
    setMode('full');
    document.getElementById('crossover').value=250;
    document.getElementById('crossover-val').textContent='250';
    document.getElementById('lo_weight').value=0.6;
    document.getElementById('lo_weight-val').textContent='0.60';
    document.getElementById('hi_weight').value=0.4;
    document.getElementById('hi_weight-val').textContent='0.40';
    monitorOn=false; bypassOn=false; soloMode='off';
    document.getElementById('btn-monitor').textContent='🔇 Monitor';
    document.getElementById('btn-monitor').classList.remove('monitor-on');
    document.getElementById('btn-bypass').classList.remove('active');
    document.getElementById('btn-solo-lo').classList.remove('solo-lo');
    document.getElementById('btn-solo-hi').classList.remove('solo-hi');
  });
}

// ── VU Canvas ──
const vuCanvas = document.getElementById('vu-canvas');
const vuCtx = vuCanvas.getContext('2d');
let needleAngle = 0; // -45..+45 degrees mapped from 0..100

function resizeVU(){
  const r = vuCanvas.parentElement.getBoundingClientRect();
  vuCanvas.width = r.width * 2;
  vuCanvas.height = r.height * 2;
  vuCtx.setTransform(2,0,0,2,0,0);
}
resizeVU();
window.addEventListener('resize', resizeVU);
setTimeout(resizeVU, 500);

function drawVU(level, peak){
  const w = vuCanvas.width/2, h = vuCanvas.height/2;
  const ctx = vuCtx;
  ctx.clearRect(0,0,w,h);

  // Center pivot point (inside canvas so needle is always visible)
  const cx = w/2;
  const cy = h - 22;
  const radius = Math.min(w * 0.45, h * 0.78);

  // Scale arc
  const arcStart = Math.PI + 0.35;
  const arcEnd = -0.35;

  // Draw scale markings
  const marks = [
    {pct:0, label:'-∞'}, {pct:10, label:'-20'}, {pct:25, label:'-10'},
    {pct:40, label:'-7'}, {pct:55, label:'-5'}, {pct:65, label:'-3'},
    {pct:75, label:'-1'}, {pct:80, label:'0'}, {pct:85, label:'+1'},
    {pct:90, label:'+2'}, {pct:95, label:'+3'}, {pct:100, label:'▮'}
  ];

  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';

  marks.forEach(m=>{
    const a = arcStart + (arcEnd - arcStart) * (m.pct/100);
    const r1 = radius - 30;
    const r2 = radius - 18;
    const r3 = radius - 8;
    const x1 = cx + r1*Math.cos(a), y1 = cy + r1*Math.sin(a);
    const x2 = cx + r2*Math.cos(a), y2 = cy + r2*Math.sin(a);
    const x3 = cx + r3*Math.cos(a), y3 = cy + r3*Math.sin(a);

    // Tick
    ctx.beginPath();
    ctx.moveTo(x1,y1);
    ctx.lineTo(x2,y2);
    ctx.strokeStyle = m.pct >= 80 ? '#c0392b' : '#3a3020';
    ctx.lineWidth = m.pct%25===0 ? 2 : 1;
    ctx.stroke();

    // Label
    ctx.font = '500 11px "DM Sans"';
    ctx.fillStyle = m.pct >= 80 ? '#c0392b' : '#5a4a38';
    ctx.fillText(m.label, x3, y3);
  });

  // "VU" label
  ctx.font = 'italic 24px "Instrument Serif"';
  ctx.fillStyle = '#8a7a60';
  ctx.fillText('VU', cx, h*0.62);

  // Sub minor ticks
  for(let p=0; p<=100; p+=2){
    const a = arcStart + (arcEnd - arcStart) * (p/100);
    const r1 = radius - 30;
    const r2 = radius - 24;
    const x1 = cx+r1*Math.cos(a), y1 = cy+r1*Math.sin(a);
    const x2 = cx+r2*Math.cos(a), y2 = cy+r2*Math.sin(a);
    ctx.beginPath();
    ctx.moveTo(x1,y1); ctx.lineTo(x2,y2);
    ctx.strokeStyle = p>=80 ? 'rgba(192,57,43,0.3)' : 'rgba(58,48,32,0.3)';
    ctx.lineWidth = 0.5;
    ctx.stroke();
  }

  // Red zone arc
  ctx.beginPath();
  const redStart = arcStart + (arcEnd-arcStart)*0.78;
  ctx.arc(cx, cy, radius-27, redStart, arcEnd);
  ctx.strokeStyle = 'rgba(192,57,43,0.25)';
  ctx.lineWidth = 4;
  ctx.stroke();

  // Needle
  const needleA = arcStart + (arcEnd - arcStart) * (level/100);
  const nLen = radius - 10;
  const nx = cx + nLen * Math.cos(needleA);
  const ny = cy + nLen * Math.sin(needleA);

  // Needle shadow
  ctx.beginPath();
  ctx.moveTo(cx+2, cy+2);
  ctx.lineTo(nx+2, ny+2);
  ctx.strokeStyle = 'rgba(0,0,0,0.15)';
  ctx.lineWidth = 3;
  ctx.stroke();

  // Needle body
  ctx.beginPath();
  ctx.moveTo(cx, cy);
  ctx.lineTo(nx, ny);
  ctx.strokeStyle = '#1a1a1a';
  ctx.lineWidth = 2;
  ctx.stroke();

  // Needle tip (red)
  const tipLen = 20;
  const tx = nx - tipLen*Math.cos(needleA);
  const ty = ny - tipLen*Math.sin(needleA);
  ctx.beginPath();
  ctx.moveTo(tx,ty); ctx.lineTo(nx,ny);
  ctx.strokeStyle = '#c0392b';
  ctx.lineWidth = 2;
  ctx.stroke();

  // Pivot dot
  ctx.beginPath();
  ctx.arc(cx, cy, 6, 0, Math.PI*2);
  ctx.fillStyle = '#2a2a2a';
  ctx.fill();
  ctx.beginPath();
  ctx.arc(cx, cy, 3, 0, Math.PI*2);
  ctx.fillStyle = '#555';
  ctx.fill();

  // Peak marker
  if(peak > 0){
    const pa = arcStart + (arcEnd-arcStart)*(peak/100);
    const pr = radius - 30;
    const px = cx+pr*Math.cos(pa), py = cy+pr*Math.sin(pa);
    ctx.beginPath();
    ctx.arc(px,py, 3, 0, Math.PI*2);
    ctx.fillStyle = '#c0392b';
    ctx.globalAlpha = 0.7;
    ctx.fill();
    ctx.globalAlpha = 1;
  }
}

// ── Physics canvas ──
const physCanvas = document.getElementById('phys-canvas');
const physCtx = physCanvas.getContext('2d');

function resizePhys(){
  const r=physCanvas.parentElement.getBoundingClientRect();
  const w = Math.max(r.width, 200);
  physCanvas.width=w*2;
  physCanvas.height=120*2;
  physCtx.setTransform(2,0,0,2,0,0);
}
resizePhys();
window.addEventListener('resize', resizePhys);
// Nochmal nach kurzer Verzögerung (Layout kann beim Laden noch nicht fertig sein)
setTimeout(resizePhys, 500);

let physHistory = [];

function drawPhysics(d){
  physHistory.push({pos:d.pos, target:d.target, vel:d.vel});
  if(physHistory.length>200) physHistory.shift();

  const w=physCanvas.width/2, h=120;
  const ctx=physCtx;
  ctx.clearRect(0,0,w,h);

  // Background grid
  ctx.strokeStyle='rgba(255,255,255,0.03)';
  ctx.lineWidth=0.5;
  for(let y=0;y<h;y+=20){ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(w,y);ctx.stroke();}

  const len=physHistory.length;
  const dx=w/200;

  // Target line (thin, grey)
  ctx.beginPath();
  ctx.strokeStyle='rgba(255,255,255,0.15)';
  ctx.lineWidth=1;
  physHistory.forEach((p,i)=>{
    const x=i*dx, y=h-(p.target/100)*h;
    i===0?ctx.moveTo(x,y):ctx.lineTo(x,y);
  });
  ctx.stroke();

  // Position line (brass)
  ctx.beginPath();
  ctx.strokeStyle='rgba(184,134,11,0.8)';
  ctx.lineWidth=1.5;
  physHistory.forEach((p,i)=>{
    const x=i*dx, y=h-(p.pos/100)*h;
    i===0?ctx.moveTo(x,y):ctx.lineTo(x,y);
  });
  ctx.stroke();

  // Velocity as filled area
  ctx.beginPath();
  ctx.fillStyle='rgba(57,255,20,0.06)';
  ctx.moveTo(0,h/2);
  physHistory.forEach((p,i)=>{
    const x=i*dx, y=h/2-(p.vel/5)*20;
    ctx.lineTo(x,Math.max(0,Math.min(h,y)));
  });
  ctx.lineTo(len*dx,h/2);
  ctx.fill();

  // Force vectors (right side)
  if(d.f_spring!==undefined){
    const bx=w-60, by=10;
    const sc=0.4;
    const drawArrow=(label, force, color, yOff)=>{
      const len=Math.min(50, Math.abs(force)*sc);
      const dir=force>0?1:-1;
      ctx.beginPath();
      ctx.moveTo(bx, by+yOff);
      ctx.lineTo(bx+len*dir, by+yOff);
      ctx.strokeStyle=color;
      ctx.lineWidth=2;
      ctx.stroke();
      // arrowhead
      ctx.beginPath();
      ctx.moveTo(bx+len*dir, by+yOff-3);
      ctx.lineTo(bx+len*dir+4*dir, by+yOff);
      ctx.lineTo(bx+len*dir, by+yOff+3);
      ctx.fillStyle=color;
      ctx.fill();
      ctx.font='500 8px "DM Sans"';
      ctx.fillStyle=color;
      ctx.textAlign='right';
      ctx.fillText(label, bx-4, by+yOff+3);
    };
    drawArrow('Feder', d.f_spring, 'rgba(79,195,247,0.7)', 15);
    drawArrow('Dämpf', d.f_damping, 'rgba(255,138,101,0.7)', 35);
    drawArrow('Grav', d.f_gravity, 'rgba(255,255,255,0.3)', 55);
  }

  // Labels
  ctx.font='500 9px "DM Sans"';
  ctx.textAlign='left';
  ctx.fillStyle='rgba(184,134,11,0.5)';
  ctx.fillText('Pos', 4, 12);
  ctx.fillStyle='rgba(255,255,255,0.2)';
  ctx.fillText('Target', 4, 24);
  ctx.fillStyle='rgba(57,255,20,0.3)';
  ctx.fillText('Vel', 4, 36);
}

// ── LED update ──
function updateLEDs(level){
  const n=Math.round(level/100*40);
  ledSegs.forEach((s,i)=>{
    if(i<n){
      if(i<24) s.style.background='var(--led-green)';
      else if(i<32) s.style.background='var(--led-amber)';
      else s.style.background='var(--led-red)';
      s.style.boxShadow=`0 0 3px ${i<24?'var(--led-green)':i<32?'var(--led-amber)':'var(--led-red)'}`;
    } else {
      s.style.background='var(--led-off)';
      s.style.boxShadow='none';
    }
  });
}

// ── Extra dials ──
function loadExtras(){
  fetch('/extra_status').then(r=>r.json()).then(data=>{
    const c=document.getElementById('extra-dials');
    if(!data.length){c.innerHTML='<div style="color:#333;font-size:0.75em">keine</div>';return;}
    c.innerHTML=data.map(d=>{
      const col=d.value>80?'var(--led-red)':d.value>60?'var(--led-amber)':'var(--led-green)';
      return `<div class="extra-card">
        <div style="display:flex;justify-content:space-between;font-size:0.82em">
          <span><span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:${d.found?'var(--led-green)':'var(--led-red)'};margin-right:6px"></span>${d.label}</span>
          <span style="color:${col};font-family:'JetBrains Mono',monospace;font-weight:700">${d.found?d.value+'%':'—'}</span>
        </div>
        <div style="background:#0a0a08;border-radius:2px;height:4px;margin-top:4px;overflow:hidden">
          <div style="height:100%;width:${d.value}%;background:${col};transition:width 0.3s"></div>
        </div>
        <div style="font-size:0.65em;color:#333;margin-top:3px;font-family:'JetBrains Mono',monospace">${d.uid_short} · ${d.status}</div>
      </div>`;
    }).join('');
  });
}
loadExtras();
setInterval(loadExtras, 1000);

// ── Poll ──
let firstPoll = true;
function pollLevel(){
  if(!isRunning) return;
  if(firstPoll){ resizePhys(); resizeVU(); firstPoll=false; }
  fetch('/level').then(r=>r.json()).then(d=>{
    const lv=d.level, pk=d.peak;
    document.getElementById('readout').textContent=Math.round(lv)+'%';
    document.getElementById('peak-val').textContent=Math.round(pk)+'%';
    if(d.db!==undefined) document.getElementById('db-val').textContent=d.db+' dB';
    if(d.db_lo!==undefined) document.getElementById('db-bands').textContent=d.db_lo+' dB lo · '+d.db_hi+' dB hi';

    drawVU(lv, pk);
    updateLEDs(lv);

    if(d.phys) drawPhysics(d.phys);

    setTimeout(pollLevel, 30);
  }).catch(()=>{
    isRunning=false;
    document.getElementById('btn-start').textContent='▶ START';
    document.getElementById('btn-start').classList.remove('running');
    document.getElementById('status').textContent='verbindung verloren';
  });
}

// Initial draw
drawVU(0,0);
drawPhysics({pos:0,vel:0,target:0,f_spring:0,f_damping:0,f_gravity:0});
</script>
</body>
</html>
"""


# ══════════════════════════════════════════════════════════════
# VU1 Hardware Client
# ══════════════════════════════════════════════════════════════

class VU1Client:
    def __init__(self, host="localhost", port=5340, api_key=""):
        self.base_url = f"http://{host}:{port}"
        self.api_key = api_key

    def get_dials(self):
        try:
            url = f"{self.base_url}/api/v0/dial/list"
            params = {"key": self.api_key} if self.api_key else {}
            r = requests.get(url, params=params, timeout=5)
            data = r.json()
            if data.get("status") == "ok":
                return data.get("data", [])
        except Exception as e:
            print(f"Dial-Fehler: {e}")
        return []

    def set_dial_value(self, uid, value):
        value = max(0, min(100, int(value)))
        try:
            url = f"{self.base_url}/api/v0/dial/{uid}/set"
            params = {"value": value}
            if self.api_key:
                params["key"] = self.api_key
            requests.get(url, params=params, timeout=0.5)
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════
# PhysicsVU — Audio Engine + Meter
# ══════════════════════════════════════════════════════════════

class PhysicsVU:
    def __init__(self, device_in=None, device_out=None):
        self.device_in = device_in
        self.device_out = device_out
        self.stream = None
        self.sample_rate = 44100

        # Physik
        self.mass = 0.8
        self.damping = 1.2
        self.spring = 3.0
        self.gravity = 0.0
        self.sensitivity = -40

        # Nadel-State
        self.needle_pos = 0.0
        self.needle_vel = 0.0
        self.peak_pos = 0.0
        self.peak_hold_t = 0.0
        self._last_time = None

        # Physik-Visualisierung: Kräfte für Frontend
        self._f_spring = 0.0
        self._f_damping = 0.0
        self._f_gravity = 0.0
        self._target = 0.0

        # Audio
        self._latest_rms = 0.0
        self._latest_peak = 0.0

        # Ringbuffer 15ms
        self._ring_size = int(self.sample_rate * 15 / 1000)
        self._ring = np.zeros(self._ring_size, dtype=np.float32)
        self._ring_idx = 0

        # Mode
        self.mode = 'full'

        # Monitor / Bypass / Solo
        self.monitor = False
        self.bypass = False
        self.solo = 'off'  # 'off','lo','hi'

        # Dual-Band
        self.band_crossover = 250.0
        self.band_lo_weight = 0.6
        self.band_hi_weight = 0.4
        self._bq_lo_z = np.zeros(2)
        self._bq_hi_z = np.zeros(2)
        self._bq_lo, self._bq_hi = self._calc_biquad(self.band_crossover)
        self._ring_lo = np.zeros(self._ring_size, dtype=np.float32)
        self._ring_hi = np.zeros(self._ring_size, dtype=np.float32)
        self._latest_rms_lo = 0.0
        self._latest_rms_hi = 0.0

        # IEC True
        self._iec_coeffs = self._calc_biquad_lpf(2.224, 0.6053)
        self._iec_z = np.zeros(2)
        self._iec_level = 0.0
        self._iec_fast = 0.0
        self.iec_transient_boost = 0.22

        # Natural+ Formel (neue Ballistik)
        self._natural_env = 0.0

    # ── Biquad helpers ──
    def _calc_biquad(self, fc):
        w0 = 2.0 * math.pi * fc / self.sample_rate
        alpha = math.sin(w0) / (2.0 * 0.7071)
        cos_w0 = math.cos(w0)
        b0_lp = (1.0 - cos_w0) / 2.0
        b1_lp = 1.0 - cos_w0
        a0 = 1.0 + alpha
        a1 = -2.0 * cos_w0
        a2 = 1.0 - alpha
        lp = np.array([b0_lp/a0, b1_lp/a0, b0_lp/a0, a1/a0, a2/a0], dtype=np.float64)
        b0_hp = (1.0 + cos_w0) / 2.0
        b1_hp = -(1.0 + cos_w0)
        hp = np.array([b0_hp/a0, b1_hp/a0, b0_hp/a0, a1/a0, a2/a0], dtype=np.float64)
        return lp, hp

    def _calc_biquad_lpf(self, fc, Q):
        w0 = 2.0 * math.pi * fc / self.sample_rate
        alpha = math.sin(w0) / (2.0 * Q)
        cos_w0 = math.cos(w0)
        b0 = (1.0 - cos_w0) / 2.0
        a0 = 1.0 + alpha
        a1 = -2.0 * cos_w0
        a2 = 1.0 - alpha
        return np.array([b0/a0, (1.0-cos_w0)/a0, b0/a0, a1/a0, a2/a0], dtype=np.float64)

    @staticmethod
    def _biquad_process(coeffs, z, x):
        b0, b1, b2, a1, a2 = coeffs
        out = np.empty_like(x, dtype=np.float64)
        z1, z2 = z[0], z[1]
        for i in range(len(x)):
            xi = float(x[i])
            yi = b0*xi + z1
            z1 = b1*xi - a1*yi + z2
            z2 = b2*xi - a2*yi
            out[i] = yi
        z[0], z[1] = z1, z2
        return out

    # ── Audio Callback (kombinierter I/O Stream) ──
    def _callback(self, indata, outdata, frames, time_info, status):
        mono = indata[:, 0] if indata.ndim > 1 else indata.flatten()

        # Peak
        self._latest_peak = float(np.max(np.abs(mono)))

        # Ringbuffer
        n = len(mono)
        end = self._ring_idx + n
        if end <= self._ring_size:
            self._ring[self._ring_idx:end] = mono
        else:
            first = self._ring_size - self._ring_idx
            self._ring[self._ring_idx:] = mono[:first]
            self._ring[:n - first] = mono[first:]

        # Dual-Band Filter
        lo_block = None
        hi_block = None
        if self.mode == 'dualband' or self.solo != 'off':
            lo_block = self._biquad_process(self._bq_lo, self._bq_lo_z, mono.astype(np.float64))
            hi_block = self._biquad_process(self._bq_hi, self._bq_hi_z, mono.astype(np.float64))
            if end <= self._ring_size:
                self._ring_lo[self._ring_idx:end] = lo_block
                self._ring_hi[self._ring_idx:end] = hi_block
            else:
                first = self._ring_size - self._ring_idx
                self._ring_lo[self._ring_idx:] = lo_block[:first]
                self._ring_lo[:n-first] = lo_block[first:]
                self._ring_hi[self._ring_idx:] = hi_block[:first]
                self._ring_hi[:n-first] = hi_block[first:]
            self._latest_rms_lo = float(np.sqrt(np.mean(self._ring_lo**2)))
            self._latest_rms_hi = float(np.sqrt(np.mean(self._ring_hi**2)))

        self._ring_idx = (self._ring_idx + n) % self._ring_size
        self._latest_rms = float(np.sqrt(np.mean(self._ring**2)))

        # IEC True
        if self.mode == 'iec_true':
            rect = np.abs(mono).astype(np.float64)
            filt = self._biquad_process(self._iec_coeffs, self._iec_z, rect)
            # Kleiner schneller Pfad gegen subjektiven Bass-Delay
            block_dt = max(1.0 / self.sample_rate, len(rect) / self.sample_rate)
            block_peak = float(np.max(rect))
            atk_t = 0.012
            rel_t = 0.140
            alpha_a = 1.0 - math.exp(-block_dt / atk_t)
            alpha_r = 1.0 - math.exp(-block_dt / rel_t)
            alpha = alpha_a if block_peak > self._iec_fast else alpha_r
            self._iec_fast += (block_peak - self._iec_fast) * alpha

            iec_slow = float(filt[-1])
            self._iec_level = ((1.0 - self.iec_transient_boost) * iec_slow +
                               self.iec_transient_boost * self._iec_fast)

        # ── Audio Output ──
        # Monitor: Signal hören (mit Filter/Solo je nach Mode)
        # Bypass:  Signal hören (raw Stereo, ungefiltert)
        # Keins:   Stille
        if outdata is not None:
            out_ch = outdata.shape[1]
            in_ch = indata.shape[1] if indata.ndim > 1 else 1
            n_frames = min(outdata.shape[0], indata.shape[0])

            def _stereo_copy():
                """Originales Stereo-Signal direkt durchreichen."""
                if in_ch >= out_ch:
                    outdata[:n_frames] = indata[:n_frames, :out_ch]
                else:
                    for ch in range(out_ch):
                        outdata[:n_frames, ch] = indata[:n_frames, min(ch, in_ch-1)]

            if self.bypass:
                # Bypass: immer raw Stereo, egal ob Monitor an/aus
                _stereo_copy()

            elif self.monitor:
                # Monitor: gefiltertes Signal je nach Solo-Modus
                if self.solo == 'lo' and lo_block is not None:
                    solo_f32 = lo_block.astype(np.float32)
                    for ch in range(out_ch):
                        outdata[:, ch] = solo_f32[:n_frames]
                elif self.solo == 'hi' and hi_block is not None:
                    solo_f32 = hi_block.astype(np.float32)
                    for ch in range(out_ch):
                        outdata[:, ch] = solo_f32[:n_frames]
                else:
                    # Monitor ohne Solo: Stereo durchreichen
                    _stereo_copy()

            else:
                # Weder Monitor noch Bypass: Stille
                outdata[:] = 0

    # ── Stream Control ──
    def start(self):
        try:
            in_info = sd.query_devices(self.device_in)
            in_ch = min(2, in_info['max_input_channels'])
            if in_ch == 0:
                print("❌ Kein Input-Kanal!")
                return False

            out_ch = 0
            if self.device_out is not None and self.device_out >= 0:
                out_info = sd.query_devices(self.device_out)
                out_ch = min(2, out_info['max_output_channels'])

            if out_ch > 0:
                self.stream = sd.Stream(
                    device=(self.device_in, self.device_out),
                    channels=(in_ch, out_ch),
                    callback=self._callback,
                    blocksize=128,
                    samplerate=self.sample_rate
                )
            else:
                # Input-only — wrap callback to match signature
                def input_only_cb(indata, frames, time_info, status):
                    self._callback(indata, None, frames, time_info, status)
                self.stream = sd.InputStream(
                    device=self.device_in,
                    channels=in_ch,
                    callback=input_only_cb,
                    blocksize=128,
                    samplerate=self.sample_rate
                )

            self.stream.start()
            self._last_time = time.perf_counter()
            print("✅ Audio gestartet")
            return True
        except Exception as e:
            print(f"Audio-Fehler: {e}")
            return False

    def stop(self):
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

    # ── dB Mapping ──
    def _rms_to_percent(self, rms):
        if rms < 1e-7:
            return 0.0
        db = 20.0 * math.log10(rms)
        db_clamped = max(self.sensitivity, min(0.0, db))
        linear = (db_clamped - self.sensitivity) / (-self.sensitivity)
        return (linear ** 1.3) * 100.0

    # ── get_level ──
    def get_level(self):
        now = time.perf_counter()
        if self._last_time is None:
            self._last_time = now
        dt = now - self._last_time
        self._last_time = now
        dt = min(dt, 0.05)

        # IEC True
        if self.mode == 'iec_true':
            corrected = self._iec_level * (math.pi / 2.0)
            self.needle_pos = self._rms_to_percent(corrected)
            self.needle_pos = max(0.0, min(100.0, self.needle_pos))
            self._target = self.needle_pos
            self._f_spring = 0; self._f_damping = 0; self._f_gravity = 0

            peak_t = self._rms_to_percent(self._latest_peak)
            if peak_t > self.peak_pos:
                self.peak_pos = peak_t; self.peak_hold_t = 1.5
            else:
                if self.peak_hold_t > 0: self.peak_hold_t -= dt
                else: self.peak_pos -= 20.0 * dt
            self.peak_pos = max(0.0, min(100.0, self.peak_pos))
            return self.needle_pos, self.peak_pos

        # Natural+ (eigene Formel):
        # 1) getrennte Attack/Release-Hüllkurve
        # 2) 2.-Ordnung Nadelmodell für natürliches Ein-/Ausschwingen
        if self.mode == 'natural_formula':
            target = self._rms_to_percent(self._latest_rms)

            atk_t = 0.085   # schneller Angriff
            rel_t = 0.650   # weicher Rücklauf
            alpha_a = 1.0 - math.exp(-dt / atk_t)
            alpha_r = 1.0 - math.exp(-dt / rel_t)
            alpha = alpha_a if target > self._natural_env else alpha_r
            self._natural_env += (target - self._natural_env) * alpha

            # 2nd-order Needle (kritisch nahe gedämpft)
            stiffness = 58.0
            damping = 14.5
            acc = stiffness * (self._natural_env - self.needle_pos) - damping * self.needle_vel
            self.needle_vel += acc * dt
            self.needle_pos += self.needle_vel * dt
            self.needle_pos = max(0.0, min(100.0, self.needle_pos))

            # Bei sehr kleinen Pegeln ruhig auf 0 setzen (kein Mikrozappeln)
            if self._natural_env < 0.3 and self.needle_pos < 0.3:
                self._natural_env = 0.0
                self.needle_pos = 0.0
                self.needle_vel *= 0.6

            self._target = self._natural_env
            self._f_spring = 0.0
            self._f_damping = 0.0
            self._f_gravity = 0.0

            peak_t = self._rms_to_percent(self._latest_peak)
            if peak_t > self.peak_pos:
                self.peak_pos = peak_t
                self.peak_hold_t = 1.2
            else:
                if self.peak_hold_t > 0:
                    self.peak_hold_t -= dt
                else:
                    self.peak_pos -= 16.0 * dt
            self.peak_pos = max(0.0, min(100.0, self.peak_pos))
            return self.needle_pos, self.peak_pos

        # Target
        if self.mode == 'dualband':
            target = min(100.0, self._rms_to_percent(self._latest_rms_lo)*self.band_lo_weight +
                         self._rms_to_percent(self._latest_rms_hi)*self.band_hi_weight)
        else:
            target = self._rms_to_percent(self._latest_rms)
        self._target = target

        # Spring-mass-damper
        self._f_spring = self.spring * (target - self.needle_pos)
        self._f_damping = -self.damping * self.needle_vel
        self._f_gravity = -self.gravity

        f_total = self._f_spring + self._f_damping + self._f_gravity
        acc = f_total / max(0.01, self.mass)
        self.needle_vel += acc * dt
        self.needle_pos += self.needle_vel * dt

        if self.needle_pos < 0:
            self.needle_pos = 0; self.needle_vel = max(0, self.needle_vel)
        elif self.needle_pos > 100:
            self.needle_pos = 100; self.needle_vel = min(0, self.needle_vel)

        peak_t = self._rms_to_percent(self._latest_peak)
        if peak_t > self.peak_pos:
            self.peak_pos = peak_t; self.peak_hold_t = 1.5
        else:
            if self.peak_hold_t > 0: self.peak_hold_t -= dt
            else: self.peak_pos -= 20.0 * dt
        self.peak_pos = max(0.0, min(100.0, self.peak_pos))

        return self.needle_pos, self.peak_pos


# ══════════════════════════════════════════════════════════════
# Flask Routes
# ══════════════════════════════════════════════════════════════

@app.route('/')
def index():
    return render_template_string(HTML_PAGE)

@app.route('/devices')
def list_devices():
    inputs, outputs = [], []
    for i, d in enumerate(sd.query_devices()):
        if d['max_input_channels'] > 0:
            inputs.append({"id": i, "name": d['name']})
        if d['max_output_channels'] > 0:
            outputs.append({"id": i, "name": d['name']})
    return jsonify({"inputs": inputs, "outputs": outputs})

@app.route('/current_device')
def current_device():
    global meter
    in_id = meter.device_in if meter else app.config.get('audio_device_in', 0)
    out_id = meter.device_out if meter else app.config.get('audio_device_out', -1)
    return jsonify({"input": in_id, "output": out_id if out_id is not None else -1})

@app.route('/set_device/<which>/<int:dev_id>')
def set_device(which, dev_id):
    global meter, running
    if which == 'in':
        if running:
            return jsonify({"ok": False, "error": "Zuerst stoppen"})
        if meter:
            meter.stop()
            meter.device_in = dev_id
        app.config['audio_device_in'] = dev_id
    elif which == 'out':
        if meter:
            was_running = running
            if running:
                running = False
                meter.stop()
            meter.device_out = dev_id if dev_id >= 0 else None
            app.config['audio_device_out'] = dev_id
            if was_running:
                if meter.start():
                    running = True
                    threading.Thread(target=update_loop, daemon=True).start()
    return jsonify({"ok": True})

@app.route('/toggle')
def toggle():
    global running, meter, current_level
    if running:
        running = False
        if meter: meter.stop()
        return jsonify({"running": False})
    else:
        if not meter:
            meter = PhysicsVU(
                device_in=app.config.get('audio_device_in'),
                device_out=app.config.get('audio_device_out')
            )
        if not meter.stream:
            if not meter.start():
                return jsonify({"running": False, "error": "Audio failed"})
        running = True
        threading.Thread(target=update_loop, daemon=True).start()
        return jsonify({"running": True})

@app.route('/level')
def get_level_route():
    global current_level, current_peak, meter
    rms = meter._latest_rms if meter else 0.0
    db = round(20 * math.log10(rms), 1) if rms > 1e-7 else -120
    resp = {"level": current_level, "peak": current_peak, "db": db}
    if meter:
        resp["phys"] = {
            "pos": round(meter.needle_pos, 2),
            "vel": round(meter.needle_vel, 2),
            "target": round(meter._target, 2),
            "f_spring": round(meter._f_spring, 2),
            "f_damping": round(meter._f_damping, 2),
            "f_gravity": round(meter._f_gravity, 2)
        }
        if meter.mode == 'dualband':
            rlo = meter._latest_rms_lo
            rhi = meter._latest_rms_hi
            resp["db_lo"] = round(20*math.log10(rlo), 1) if rlo > 1e-7 else -120
            resp["db_hi"] = round(20*math.log10(rhi), 1) if rhi > 1e-7 else -120
    return jsonify(resp)

@app.route('/extra_status')
def extra_status():
    result = []
    cpu = int(psutil.cpu_percent(interval=None))
    result.append({"label":"CPU","found":bool(cpu_dial_uid),"value":cpu if cpu_dial_uid else 0,
                    "uid_short":cpu_dial_uid[:8]+"…" if cpu_dial_uid else "—",
                    "status":"aktiv" if cpu_dial_uid else "kein Dial"})
    disk = int(psutil.disk_usage('/').percent)
    result.append({"label":"Disk /","found":bool(disk_dial_uid),"value":disk if disk_dial_uid else 0,
                    "uid_short":disk_dial_uid[:8]+"…" if disk_dial_uid else "—",
                    "status":"aktiv" if disk_dial_uid else "kein Dial"})
    return jsonify(result)

@app.route('/set/<param>/<value>')
def set_param(param, value):
    global meter
    if not meter: return jsonify({"ok": False})
    if param == 'mode':
        meter.mode = value
        if value == 'iec_true':
            meter._iec_z[:] = 0
            meter._iec_fast = meter._latest_peak
        if value == 'natural_formula':
            meter._natural_env = meter.needle_pos
    elif param == 'monitor':
        meter.monitor = value == '1'
    elif param == 'bypass':
        meter.bypass = value == '1'
    elif param == 'solo':
        meter.solo = value
    elif param == 'crossover':
        meter.band_crossover = float(value)
        meter._bq_lo, meter._bq_hi = meter._calc_biquad(float(value))
        meter._bq_lo_z[:] = 0; meter._bq_hi_z[:] = 0
    elif param == 'lo_weight':
        meter.band_lo_weight = float(value)
    elif param == 'hi_weight':
        meter.band_hi_weight = float(value)
    else:
        v = float(value)
        if param == 'mass': meter.mass = v
        elif param == 'damping': meter.damping = v
        elif param == 'spring': meter.spring = v
        elif param == 'gravity': meter.gravity = v
        elif param == 'sensitivity': meter.sensitivity = v
    return jsonify({"ok": True})

@app.route('/reset')
def reset():
    global meter
    if meter:
        meter.mass=0.8; meter.damping=1.2; meter.spring=3.0
        meter.gravity=0.0; meter.sensitivity=-40
        meter.needle_pos=0; meter.needle_vel=0; meter.peak_pos=0
        meter.mode='full'; meter.monitor=False; meter.bypass=False; meter.solo='off'
        meter.band_crossover=250; meter.band_lo_weight=0.6; meter.band_hi_weight=0.4
        meter._iec_z[:]=0; meter._iec_level=0; meter._iec_fast=0; meter._natural_env=0
    return jsonify({"ok": True})


# ── Helpers ──

def value_to_backlight(pct):
    if pct < 60: return {"red":0,"green":100,"blue":0}
    elif pct < 80: return {"red":100,"green":60,"blue":0}
    else: return {"red":100,"green":0,"blue":0}

def send_metric(uid, value):
    try:
        client.set_dial_value(uid, value)
        bl = value_to_backlight(value)
        url = f"{client.base_url}/api/v0/dial/{uid}/backlight"
        requests.get(url, params={**bl, "key": client.api_key}, timeout=0.5)
    except Exception: pass

def update_loop():
    global running, current_level, current_peak, meter, client
    global dial_uid, cpu_dial_uid, disk_dial_uid
    psutil.cpu_percent(interval=None)
    while running:
        if meter:
            current_level, current_peak = meter.get_level()
            if client and dial_uid:
                threading.Thread(target=send_metric, args=(dial_uid, current_level), daemon=True).start()
        if client and cpu_dial_uid:
            cpu = int(psutil.cpu_percent(interval=None))
            threading.Thread(target=send_metric, args=(cpu_dial_uid, cpu), daemon=True).start()
        if client and disk_dial_uid:
            disk = int(psutil.disk_usage('/').percent)
            threading.Thread(target=send_metric, args=(disk_dial_uid, disk), daemon=True).start()
        time.sleep(0.015)


# ── Main ──

def main():
    global client, dial_uid, meter

    parser = argparse.ArgumentParser()
    parser.add_argument("--api-key", required=True)
    parser.add_argument("--audio-device", type=int, default=None)
    parser.add_argument("--output-device", type=int, default=None)
    parser.add_argument("--dial-name", default="CPU")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()

    app.config['audio_device_in'] = args.audio_device
    app.config['audio_device_out'] = args.output_device

    client = VU1Client(api_key=args.api_key)
    dials = client.get_dials()

    found_uid = None
    for d in dials:
        if d['dial_name'].upper() == args.dial_name.upper():
            found_uid = d['uid']
            print(f"✅ Audio-Dial:  {d['dial_name']} ({d['uid'][:8]}…)")
            break
    if not found_uid:
        print(f"❌ Dial '{args.dial_name}' nicht gefunden!")
        sys.exit(1)
    globals()['dial_uid'] = found_uid

    others = [d['uid'] for d in dials if d['uid'] != found_uid]
    if len(others) >= 1:
        globals()['cpu_dial_uid'] = others[0]
        print(f"✅ CPU-Dial:    ({others[0][:8]}…)")
    if len(others) >= 2:
        globals()['disk_dial_uid'] = others[1]
        print(f"✅ Disk-Dial:   ({others[1][:8]}…)")

    meter = PhysicsVU(device_in=args.audio_device, device_out=args.output_device)

    print(f"\n🎛️  VU1 Meter Web GUI v3")
    print(f"{'='*40}")
    print(f"http://localhost:{args.port}")
    print(f"{'='*40}")

    app.run(host='0.0.0.0', port=args.port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
