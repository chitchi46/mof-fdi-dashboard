from __future__ import annotations

import http.server
import os
import socketserver
import cgi
import json
import uuid

from .normalize import normalize_file, build_summary_multi_measure, SCHEMA_HEADERS
from .io import write_csv
from .schema import schema_meta


INDEX_HTML = """<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>InvestViz Dashboard (MVP)</title>
  <style>
    :root { --bg:#0b1220; --fg:#e5e7eb; --muted:#94a3b8; --panel:#111827; --accent:#60a5fa; --grid:#1f2937; }
    body { font-family: system-ui, -apple-system, Segoe UI, Roboto, 'Noto Sans JP', sans-serif; margin:0; background:var(--bg); color:var(--fg); }
    header { padding:12px 16px; background:#0f172a; color:#fff; display:flex; align-items:center; justify-content:space-between; }
    header .title { font-weight:700; }
    header .actions { display:flex; gap:8px; align-items:center; }
    .btn { padding:6px 12px; background:#2563eb; color:#fff; border:none; border-radius:6px; cursor:pointer; font-size:14px; }
    .btn:hover { background:#1d4ed8; }
    .btn:disabled { background:#475569; cursor:not-allowed; }
    main { padding: 16px; }
    .panel { background:var(--panel); border-radius:8px; padding:12px; border:1px solid #1f2937; }
    #controls { display:none; flex-direction:column; gap:8px; margin-bottom:12px; }
    .control-row { display:flex; flex-wrap:wrap; gap:12px; align-items:center; padding:8px; border-radius:6px; }
    .control-row.common { background:rgba(96,165,250,0.05); border:1px solid rgba(96,165,250,0.2); }
    .control-row.specific { background:rgba(148,163,184,0.05); border:1px solid rgba(148,163,184,0.2); }
    select, button, input[type=checkbox] { background:#0f172a; color:#e5e7eb; border:1px solid #334155; border-radius:6px; padding:6px 8px; }
    #chartPanel { display:none; }
    #chart { width:100%; height:420px; border:1px solid #334155; border-radius:8px; background:#0b1220; }
    .multi-panel-grid { display:grid; grid-template-columns: 1fr 1fr; grid-template-rows: 1fr 1fr; gap:12px; width:100%; height:860px; }
    .panel-item { border:1px solid #334155; border-radius:8px; background:#0b1220; position:relative; }
    .panel-item canvas { width:100%; height:100%; }
    .panel-title { position:absolute; top:8px; left:12px; font-size:13px; font-weight:bold; color:#94a3b8; pointer-events:none; }
    .meta { color: var(--muted); font-size: 12px; margin-top: 8px; }
    .legend { display:flex; flex-wrap:wrap; gap:12px; margin:8px 0; }
    .legend .item { display:flex; align-items:center; gap:6px; color: var(--muted); }
    .swatch { display:inline-block; width:12px; height:12px; border-radius:2px; }
    .drop { border:1px dashed #334155; border-radius:8px; padding:18px; text-align:center; color:var(--muted); }
    .toast { position:fixed; top:20px; right:20px; background:#0f172a; color:#e5e7eb; padding:12px 20px; border-radius:8px; border:1px solid #334155; box-shadow:0 4px 12px rgba(0,0,0,0.5); z-index:1000; display:none; }
    .toast.show { display:block; animation:slideIn 0.3s ease-out; }
    @keyframes slideIn { from {transform:translateX(400px); opacity:0;} to {transform:translateX(0); opacity:1;} }
  </style>
  <script>
let gData = null;
// Okabe-Ito 色弱対応パレット（8色）+ 補完色
let gColors = [
  '#0173B2',  // blue
  '#DE8F05',  // orange
  '#029E73',  // green
  '#CC78BC',  // purple
  '#CA9161',  // tan
  '#949494',  // gray
  '#ECE133',  // yellow
  '#56B4E9',  // sky blue
  '#D55E00',  // vermillion
  '#F0E442'   // light yellow
];
let gOverlay = false;
let gSessionId = null;  // 現在のセッションID
let gPinnedPoint = null;  // ピン留めされた点 {x, y, idx}

// 文字列から一貫した色を生成（ハッシュベース）
function stringToColor(str) {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = str.charCodeAt(i) + ((hash << 5) - hash);
  }
  return gColors[Math.abs(hash) % gColors.length];
}

// TopNスライダの値を更新
function updateTopNLabel() {
  const val = document.getElementById('topN').value;
  document.getElementById('topNValue').textContent = val;
}

// トースト表示
function showToast(message, duration = 3000) {
  const toast = document.getElementById('toast');
  toast.textContent = message;
  toast.classList.add('show');
  setTimeout(() => {
    toast.classList.remove('show');
  }, duration);
}

async function uploadAndAnalyze(file){
  const st = document.getElementById('uploadStatus');
  st.textContent = 'アップロード中...';
  const fd = new FormData(); fd.append('file', file, file.name || 'uploaded.csv');
  const res = await fetch('/api/upload', { method:'POST', body: fd });
  if (!res.ok) { st.textContent = 'アップロードに失敗しました'; return; }
  const obj = await res.json();
  gData = obj.summary;
  // セッションIDを抽出（links.normalized_csv から）
  if (obj.links && obj.links.normalized_csv) {
    const match = obj.links.normalized_csv.match(/\/uploads\/([^\/]+)\//);
    if (match) {
      gSessionId = match[1];
    }
  }
  document.getElementById('title').textContent = (gData.title || 'MVP Summary');
  const ms = document.getElementById('measure');
  ms.innerHTML='';
  (gData.series||[]).forEach((s,i)=>{ const o=document.createElement('option'); o.value=i; o.textContent=s.label||`series_${i}`; ms.appendChild(o); });
  // 地域フィルタの構築
  const regions = (gData.regions && gData.regions.available) || [];
  if (regions.length > 0) {
    const rf = document.getElementById('regionFilter');
    rf.innerHTML = '<option value="">全地域</option>';
    regions.forEach(r => { const o = document.createElement('option'); o.value = r; o.textContent = r; rf.appendChild(o); });
    document.getElementById('regionFilterLabel').style.display = '';
  } else {
    document.getElementById('regionFilterLabel').style.display = 'none';
  }
  document.getElementById('controls').style.display = 'flex';
  document.getElementById('chartPanel').style.display = 'block';
  // アップローダーは非表示にするが、ボタンで再表示可能
  hideUploadPanel();
  document.getElementById('downloadNormalized').href = obj.links.normalized_csv;
  document.getElementById('downloadNormalized').style.pointerEvents = 'auto';
  document.getElementById('downloadParseLog').href = obj.links.parse_log;
  document.getElementById('downloadParseLog').style.pointerEvents = 'auto';
  if (obj.links.pivot_csv){
    document.getElementById('downloadPivot').href = obj.links.pivot_csv;
    document.getElementById('downloadPivot').style.pointerEvents = 'auto';
  }
  st.textContent = '✓ アップロード完了';
  setTimeout(() => { st.textContent = ''; }, 3000);
  draw();
}

function showUploadPanel() {
  document.getElementById('uploader').style.display = 'block';
  document.getElementById('chartPanel').style.display = gData ? 'block' : 'none';
}

function hideUploadPanel() {
  document.getElementById('uploader').style.display = 'none';
}

function onSelectFile(){ const el=document.getElementById('file'); if(el.files && el.files[0]) uploadAndAnalyze(el.files[0]); }

// マルチパネル描画関数
function drawMultiPanel() {
  const midx = parseInt(document.getElementById('measure').value || '0', 10) || 0;
  const series = (gData.series || [])[midx] || {x:[], y:[], label:'series'};
  
  // パネル1: 時系列推移
  drawPanelChart('chart1', series, 'timeseries');
  // パネル2: 前年比差分
  drawPanelChart('chart2', series, 'yoy_diff');
  // パネル3: 国別ランキング (Top 5)
  drawPanelCountryRanking('chart3');
  // パネル4: 構成比
  drawPanelComposition('chart4');
}

// パネル用チャート描画（時系列/YoY）
function drawPanelChart(canvasId, series, mode) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const rect = canvas.getBoundingClientRect();
  canvas.width = rect.width * devicePixelRatio;
  canvas.height = rect.height * devicePixelRatio;
  ctx.setTransform(devicePixelRatio,0,0,devicePixelRatio,0,0);
  ctx.clearRect(0,0,rect.width,rect.height);

  const margin = {l: 50, r: 15, t: 35, b: 50};
  const W = rect.width - margin.l - margin.r;
  const H = rect.height - margin.t - margin.b;
  ctx.save();
  ctx.translate(margin.l, margin.t);

  let xs = series.x.slice();
  let ys = series.y.map(Number);
  if (mode === 'yoy_diff') {
    const diff = [];
    for (let i=0; i<ys.length; i++) diff.push(i ? ys[i]-ys[i-1] : 0);
    ys = diff;
  }
  
  if (xs.length === 0) { ctx.fillStyle = '#94a3b8'; ctx.fillText('データなし', 10, 20); ctx.restore(); return; }
  
  let minY = Math.min(...ys);
  let maxY = Math.max(...ys);
  const padY = (maxY - minY) * 0.1 || 1;
  const y0 = minY - padY;
  const y1 = maxY + padY;
  const xScale = i => (i/(xs.length-1)) * W;
  const yScale = v => H - ((v - y0)/(y1 - y0)) * H;
  
  // Axes
  ctx.strokeStyle = '#334155'; ctx.lineWidth = 1.5;
  ctx.beginPath(); ctx.moveTo(0,H); ctx.lineTo(W,H); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(0,0); ctx.lineTo(0,H); ctx.stroke();
  
  // Ticks
  ctx.fillStyle = '#cbd5e1'; ctx.textAlign = 'right'; ctx.textBaseline = 'middle'; ctx.font = '10px system-ui';
  const ticks = 4;
  for (let i=0;i<=ticks;i++){
    const v = y0 + (i/ticks)*(y1-y0);
    const y = yScale(v);
    ctx.strokeStyle = '#1e293b'; ctx.lineWidth = 0.5; ctx.beginPath(); ctx.moveTo(0,y); ctx.lineTo(W,y); ctx.stroke();
    ctx.fillText(v.toFixed(0), -5, y);
  }
  
  // X labels (省略版)
  ctx.textAlign = 'center'; ctx.textBaseline = 'top'; ctx.fillStyle = '#cbd5e1'; ctx.font = '9px system-ui';
  const step = Math.ceil(xs.length / 4);
  for (let i=0;i<xs.length;i+=step){ ctx.fillText(String(xs[i]), xScale(i), H+8); }
  
  // Line
  ctx.strokeStyle = gColors[0]; ctx.lineWidth = 2; ctx.beginPath();
  for (let i=0;i<ys.length;i++){ const x = xScale(i), y = yScale(ys[i]); if (i===0) ctx.moveTo(x,y); else ctx.lineTo(x,y);} ctx.stroke();
  
  ctx.restore();
}

// パネル用国別ランキング
function drawPanelCountryRanking(canvasId) {
  if (!gData || !gData.countries || !gData.countries.series) return;
  
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const rect = canvas.getBoundingClientRect();
  canvas.width = rect.width * devicePixelRatio;
  canvas.height = rect.height * devicePixelRatio;
  ctx.setTransform(devicePixelRatio,0,0,devicePixelRatio,0,0);
  ctx.clearRect(0,0,rect.width,rect.height);

  const margin = {l: 80, r: 15, t: 35, b: 40};
  const W = rect.width - margin.l - margin.r;
  const H = rect.height - margin.t - margin.b;
  ctx.save();
  ctx.translate(margin.l, margin.t);

  // 最新年のデータでトップ5を取得
  const latestYear = gData.years ? gData.years[gData.years.length - 1] : null;
  if (!latestYear) { ctx.fillStyle = '#94a3b8'; ctx.fillText('データなし', 10, 20); ctx.restore(); return; }
  
  let countryData = [];
  gData.countries.series.forEach(s => {
    const yearIdx = s.x.indexOf(latestYear);
    if (yearIdx >= 0) {
      const value = Number(s.y[yearIdx]) || 0;
      if (value > 0) countryData.push({label: s.label, value});
    }
  });
  
  countryData.sort((a, b) => b.value - a.value);
  const top5 = countryData.slice(0, 5);
  
  if (top5.length === 0) { ctx.fillStyle = '#94a3b8'; ctx.fillText('データなし', 10, 20); ctx.restore(); return; }
  
  const maxVal = Math.max(...top5.map(d => d.value));
  const barHeight = Math.max(15, Math.floor(H / (top5.length * 1.5)));
  const gap = Math.max(5, Math.floor(barHeight * 0.3));
  
  // Bars
  ctx.textAlign = 'right'; ctx.textBaseline = 'middle'; ctx.font = '10px system-ui';
  top5.forEach((d, i) => {
    const barW = (d.value / maxVal) * W * 0.9;
    const y = i * (barHeight + gap);
    const color = stringToColor(d.label);
    ctx.fillStyle = color;
    ctx.fillRect(0, y, barW, barHeight);
    // Label
    ctx.fillStyle = '#e2e8f0';
    ctx.fillText(d.label, -5, y + barHeight/2);
    // Value
    ctx.fillStyle = '#cbd5e1'; ctx.textAlign = 'left';
    ctx.fillText(d.value.toLocaleString(), barW + 5, y + barHeight/2);
    ctx.textAlign = 'right';
  });
  
  ctx.restore();
}

// パネル用構成比
function drawPanelComposition(canvasId) {
  const comp = gData.composition || {labels:[], share:[]};
  const labels = comp.labels || [];
  const share = (comp.share || []).map(Number);
  
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const rect = canvas.getBoundingClientRect();
  canvas.width = rect.width * devicePixelRatio;
  canvas.height = rect.height * devicePixelRatio;
  ctx.setTransform(devicePixelRatio,0,0,devicePixelRatio,0,0);
  ctx.clearRect(0,0,rect.width,rect.height);

  const margin = {l: 15, r: 15, t: 35, b: 15};
  const W = rect.width - margin.l - margin.r;
  const H = rect.height - margin.t - margin.b;
  ctx.save();
  ctx.translate(margin.l, margin.t);
  
  if (labels.length === 0) { ctx.fillStyle = '#94a3b8'; ctx.fillText('データなし', 10, 20); ctx.restore(); return; }
  
  // Bar chart (横向き)
  const barW = Math.max(8, Math.min(30, Math.floor(W / (labels.length*1.2))));
  const gap = Math.max(6, Math.floor(barW * 0.2));
  const maxShare = Math.max(...share);
  
  ctx.textAlign = 'center'; ctx.textBaseline = 'top'; ctx.font = '9px system-ui';
  for (let i=0; i<labels.length; i++){
    const barH = (share[i] / maxShare) * H * 0.85;
    const x = i * (barW + gap);
    const y = H - barH;
    ctx.fillStyle = gColors[i % gColors.length];
    ctx.fillRect(x, y, barW, barH);
    // Label (縦書き省略)
    ctx.fillStyle = '#cbd5e1';
    ctx.fillText(labels[i].substring(0, 5), x + barW/2, H + 5);
  }
  
  ctx.restore();
}

function draw(){
  if (!gData) return;
  const view = document.getElementById('view').value;
  
  // マルチパネルモードの場合
  if (view === 'multi_panel') {
    drawMultiPanel();
    return;
  }
  
  const canvas = document.getElementById('chart');
  const ctx = canvas.getContext('2d');
  const rect = canvas.getBoundingClientRect();
  canvas.width = rect.width * devicePixelRatio;
  canvas.height = rect.height * devicePixelRatio;
  ctx.setTransform(devicePixelRatio,0,0,devicePixelRatio,0,0);
  ctx.clearRect(0,0,rect.width,rect.height);

  const margin = {l: 60, r: 20, t: 30, b: 65};
  const W = rect.width - margin.l - margin.r;
  const H = rect.height - margin.t - margin.b;
  ctx.save();
  ctx.translate(margin.l, margin.t);
  const selectedRegion = document.getElementById('regionFilter') ? document.getElementById('regionFilter').value : '';
  
  // 地域フィルタが選択されている場合は地域データを使用
  let series;
  if (selectedRegion && gData.regions && gData.regions.series) {
    const regionSeries = gData.regions.series.find(s => s.label === selectedRegion);
    series = regionSeries || {x:[], y:[], label:selectedRegion};
  } else {
    const midx = parseInt(document.getElementById('measure').value || '0', 10) || 0;
    series = (gData.series || [])[midx] || {x:[], y:[], label:'series'};
  }

  if (view === 'timeseries' || view === 'yoy_diff') {
    let xs = series.x.slice();
    let ys = series.y.map(Number);
    if (view === 'yoy_diff') {
      const diff = [];
      for (let i=0; i<ys.length; i++) diff.push(i ? ys[i]-ys[i-1] : 0);
      ys = diff;
    }
    if (xs.length === 0) { ctx.fillText('データがありません', 10, 20); ctx.restore(); return; }
    let minY = Math.min(...ys);
    let maxY = Math.max(...ys);
    const padY = (maxY - minY) * 0.1 || 1;
    const y0 = minY - padY;
    const y1 = maxY + padY;
    const xScale = i => (i/(xs.length-1)) * W;
    const yScale = v => H - ((v - y0)/(y1 - y0)) * H;
    // Axes + grid
    ctx.strokeStyle = '#334155'; ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.moveTo(0,H); ctx.lineTo(W,H); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(0,0); ctx.lineTo(0,H); ctx.stroke();
    // Ticks (Y)
    ctx.fillStyle = '#cbd5e1'; ctx.textAlign = 'right'; ctx.textBaseline = 'middle'; ctx.font = '12px system-ui';
    const ticks = 5;
    for (let i=0;i<=ticks;i++){
      const v = y0 + (i/ticks)*(y1-y0);
      const y = yScale(v);
      ctx.strokeStyle = '#1e293b'; ctx.lineWidth = 0.5; ctx.beginPath(); ctx.moveTo(0,y); ctx.lineTo(W,y); ctx.stroke();
      ctx.fillText(v.toFixed(0), -8, y);
    }
    // Y軸ラベル
    ctx.save();
    ctx.translate(-45, H/2);
    ctx.rotate(-Math.PI/2);
    ctx.fillStyle = '#e2e8f0'; ctx.textAlign = 'center'; ctx.font = 'bold 13px system-ui';
    ctx.fillText('億円', 0, 0);
    ctx.restore();
    // X labels
    ctx.textAlign = 'center'; ctx.textBaseline = 'top'; ctx.fillStyle = '#cbd5e1'; ctx.font = '12px system-ui';
    const step = Math.ceil(xs.length / 8);
    for (let i=0;i<xs.length;i+=step){ ctx.fillText(String(xs[i]), xScale(i), H+10); }
    // X軸ラベル
    ctx.fillStyle = '#e2e8f0'; ctx.textAlign = 'center'; ctx.font = 'bold 13px system-ui';
    ctx.fillText('年度', W/2, H+35);
    // Lines
    function drawLine(lineXs, lineYs, color){
      ctx.strokeStyle = color; ctx.lineWidth = 2.5; ctx.beginPath();
      for (let i=0;i<lineYs.length;i++){ const x = xScale(i), y = yScale(lineYs[i]); if (i===0) ctx.moveTo(x,y); else ctx.lineTo(x,y);} ctx.stroke();
    }
    function drawTrendLine(ys, color) {
      // 移動平均（3点）
      if (ys.length < 3) return;
      const smoothed = [];
      for (let i=0; i<ys.length; i++) {
        if (i === 0) smoothed.push(ys[i]);
        else if (i === ys.length - 1) smoothed.push(ys[i]);
        else smoothed.push((ys[i-1] + ys[i] + ys[i+1]) / 3);
      }
      ctx.strokeStyle = color; ctx.lineWidth = 2; ctx.setLineDash([5, 5]); ctx.beginPath();
      for (let i=0;i<smoothed.length;i++){ const x = xScale(i), y = yScale(smoothed[i]); if (i===0) ctx.moveTo(x,y); else ctx.lineTo(x,y);} ctx.stroke();
      ctx.setLineDash([]);
    }
    if (gOverlay) {
      (gData.series||[]).forEach((s,i)=>{ drawLine(s.x, s.y.map(Number), gColors[i%gColors.length]); });
    } else {
      drawLine(xs, ys, gColors[0]);
      // トレンドライン
      if (document.getElementById('showTrend') && document.getElementById('showTrend').checked) {
        drawTrendLine(ys, '#f59e0b');
      }
    }
    // Title
    ctx.fillStyle = '#e5e7eb'; ctx.textAlign = 'left'; ctx.textBaseline = 'alphabetic'; ctx.font = 'bold 14px system-ui';
    const ttl = gOverlay ? '上位系列（重ね描画）' : (series.label + (view==='yoy_diff'?'（前年比差分）':''));
    ctx.fillText(ttl, 0, -8);
    // Crosshair & tooltips
    const tip = document.getElementById('status');
    let hoverIdx = -1;
    canvas.onmousemove = (ev)=>{
      const rect2 = canvas.getBoundingClientRect();
      const mx = (ev.clientX - rect2.left) - margin.l;
      const my = (ev.clientY - rect2.top) - margin.t;
      if (mx<0 || mx>W || my<0 || my>H) { tip.textContent = ''; hoverIdx = -1; draw(); return; }
      const idx = Math.round((mx/W) * (xs.length-1));
      hoverIdx = idx;
      let txt = '';
      if (gOverlay){
        const parts = (gData.series||[]).map((s,i)=>`${s.label}: ${Number(s.y[idx]||0).toLocaleString()}`);
        txt = `${xs[idx]} — ${parts.join(' / ')}`;
      } else {
        const val = Number(ys[idx]||0);
        const prevVal = idx > 0 ? Number(ys[idx-1]||0) : null;
        let yoyStr = '';
        if (prevVal !== null && prevVal !== 0) {
          const yoyPct = ((val - prevVal) / prevVal * 100).toFixed(1);
          yoyStr = ` (YoY: ${yoyPct > 0 ? '+' : ''}${yoyPct}%)`;
        }
        txt = `${xs[idx]} — ${val.toLocaleString()} ${yoyStr} (${series.label})`;
      }
      tip.textContent = txt;
      // Redraw with crosshair
      draw();
    };
    canvas.onclick = (ev)=>{
      const rect2 = canvas.getBoundingClientRect();
      const mx = (ev.clientX - rect2.left) - margin.l;
      const my = (ev.clientY - rect2.top) - margin.t;
      if (mx<0 || mx>W || my<0 || my>H) { gPinnedPoint = null; draw(); return; }
      const idx = Math.round((mx/W) * (xs.length-1));
      gPinnedPoint = {idx, x: xScale(idx), y: yScale(ys[idx])};
      draw();
    };
    // Draw crosshair & pinned point
    if (hoverIdx >= 0 && !gPinnedPoint) {
      const hx = xScale(hoverIdx);
      const hy = yScale(ys[hoverIdx]);
      ctx.strokeStyle = '#94a3b8'; ctx.lineWidth = 1; ctx.setLineDash([4, 4]);
      ctx.beginPath(); ctx.moveTo(hx, 0); ctx.lineTo(hx, H); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(0, hy); ctx.lineTo(W, hy); ctx.stroke();
      ctx.setLineDash([]);
      // Dot
      ctx.fillStyle = gColors[0]; ctx.beginPath(); ctx.arc(hx, hy, 5, 0, Math.PI*2); ctx.fill();
    }
    if (gPinnedPoint) {
      ctx.strokeStyle = '#f59e0b'; ctx.lineWidth = 1.5; ctx.setLineDash([]);
      ctx.beginPath(); ctx.moveTo(gPinnedPoint.x, 0); ctx.lineTo(gPinnedPoint.x, H); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(0, gPinnedPoint.y); ctx.lineTo(W, gPinnedPoint.y); ctx.stroke();
      ctx.fillStyle = '#f59e0b'; ctx.beginPath(); ctx.arc(gPinnedPoint.x, gPinnedPoint.y, 6, 0, Math.PI*2); ctx.fill();
    }
  } else if (view === 'composition') {
    const comp = gData.composition || {labels:[], share:[]};
    const labels = comp.labels || [];
    const share = (comp.share || []).map(Number);
    if (labels.length === 0) { ctx.fillText('構成比データがありません', 10, 20); ctx.restore(); return; }
    // Bar chart
    const barW = Math.max(8, Math.min(48, Math.floor(W / (labels.length*1.5))));
    const gap = Math.max(8, Math.floor(barW * 0.25));
    ctx.textAlign = 'center'; ctx.textBaseline = 'top';
    for (let i=0; i<labels.length; i++){
      const x = i * (barW + gap);
      const h = Math.round((share[i]) * H);
      ctx.fillStyle = gColors[i%gColors.length]; ctx.fillRect(x, H - h, barW, h);
      ctx.fillStyle = '#94a3b8'; ctx.fillText(`${labels[i].slice(0,12)} ${(share[i]*100).toFixed(1)}%`, x + barW/2, H + 8);
    }
    ctx.fillStyle = '#e5e7eb'; ctx.textAlign = 'left'; ctx.textBaseline = 'alphabetic'; ctx.font = 'bold 14px system-ui';
    ctx.fillText('構成比（' + (comp.year || '最新年') + '）', 0, -6);
  } else if (view === 'heatmap') {
    // Heatmap: measures (rows) × years (columns)
    const years = (gData.years||[]).slice();
    const seriesAll = (gData.series||[]);
    if (!years.length || !seriesAll.length) { ctx.fillText('ヒートマップ用データが不足しています', 10, 20); ctx.restore(); return; }
    // Build matrix and min/max for color scaling
    const M = seriesAll.length, N = years.length;
    const val = Array.from({length:M},()=>Array(N).fill(0));
    let vmin = Infinity, vmax = -Infinity;
    for (let i=0;i<M;i++){
      const s = seriesAll[i];
      const yi = {};
      (s.x||[]).forEach((x,idx)=>{ yi[String(x)] = Number(s.y[idx]||0);});
      for (let j=0;j<N;j++){
        const v = Number(yi[String(years[j])] || 0);
        val[i][j] = v; vmin = Math.min(vmin, v); vmax = Math.max(vmax, v);
      }
    }
    if (!isFinite(vmin) || !isFinite(vmax)) { vmin=0; vmax=1; }
    // Color scale (simple blue -> red)
    function color(t){ // t in [0,1]
      const r = Math.round(255 * t);
      const b = Math.round(255 * (1 - t));
      const g = Math.round(64 + 128 * t*(1-t));
      return `rgb(${r},${g},${b})`;
    }
    const cw = Math.max(6, Math.min(32, Math.floor(W / Math.max(6,N))));
    const ch = Math.max(12, Math.min(28, Math.floor(H / Math.max(3,M))));
    // Axes labels
    ctx.fillStyle = '#94a3b8'; ctx.textAlign='center'; ctx.textBaseline='top';
    const xstep = Math.ceil(N/10);
    for (let j=0;j<N;j+=xstep){ ctx.fillText(String(years[j]), j*cw + cw/2, H+8); }
    ctx.textAlign='right'; ctx.textBaseline='middle';
    for (let i=0;i<M;i++){ ctx.fillText(String(seriesAll[i].label||''), -8, i*ch + ch/2); }
    // Cells
    for (let i=0;i<M;i++){
      for (let j=0;j<N;j++){
        const t = (val[i][j] - vmin) / (vmax - vmin || 1);
        ctx.fillStyle = color(Math.max(0, Math.min(1,t)));
        ctx.fillRect(j*cw, i*ch, cw-1, ch-1);
      }
    }
    // Title
    ctx.fillStyle = '#e5e7eb'; ctx.textAlign='left'; ctx.textBaseline='alphabetic'; ctx.font='bold 14px system-ui';
    ctx.fillText('ヒートマップ（年×系列）', 0, -8);
  } else if (view === 'boxplot') {
    // Boxplot: distribution across series per year
    const years = (gData.years||[]).slice();
    const seriesAll = (gData.series||[]);
    if (!years.length || !seriesAll.length) { ctx.fillText('箱ひげ図用データが不足しています', 10, 20); ctx.restore(); return; }
    const N = years.length;
    const xScale = i => (N<=1? W/2 : (i/(N-1))*W);
    // Collect values per year
    function stats(vals){
      const arr = vals.slice().sort((a,b)=>a-b);
      const n = arr.length; if (!n) return null;
      function q(p){ const idx=(n-1)*p; const i=Math.floor(idx); const f=idx-i; return f? arr[i]*(1-f)+arr[i+1]*f : arr[i]; }
      return {min:arr[0], q1:q(0.25), med:q(0.5), q3:q(0.75), max:arr[n-1]};
    }
    const perYearStats = [];
    let gmin = Infinity, gmax = -Infinity;
    for (let j=0;j<N;j++){
      const vals = [];
      for (let i=0;i<seriesAll.length;i++){
        const s = seriesAll[i];
        const yi = {};
        (s.x||[]).forEach((x,idx)=>{ yi[String(x)] = Number(s.y[idx]||0);});
        const v = Number(yi[String(years[j])] || 0);
        if (isFinite(v)) vals.push(v);
      }
      const st = stats(vals);
      perYearStats.push(st);
      if (st){ gmin = Math.min(gmin, st.min); gmax = Math.max(gmax, st.max); }
    }
    if (!isFinite(gmin) || !isFinite(gmax)) { gmin=0; gmax=1; }
    const padY = (gmax-gmin)*0.1 || 1; const y0=gmin-padY, y1=gmax+padY;
    const yScale = v => H - ((v - y0)/(y1 - y0)) * H;
    // Grid
    ctx.strokeStyle = '#1f2937'; ctx.lineWidth=1; ctx.beginPath(); ctx.moveTo(0,H); ctx.lineTo(W,H); ctx.stroke(); ctx.beginPath(); ctx.moveTo(0,0); ctx.lineTo(0,H); ctx.stroke();
    ctx.fillStyle = '#94a3b8'; ctx.textAlign='center'; ctx.textBaseline='top';
    const step = Math.ceil(N/8);
    for (let j=0;j<N;j+=step){ ctx.fillText(String(years[j]), xScale(j), H+10); }
    // Draw boxes
    ctx.strokeStyle = '#60a5fa'; ctx.fillStyle = 'rgba(96,165,250,0.25)';
    const boxW = Math.max(6, Math.min(24, Math.floor(W / Math.max(6,N))));
    for (let j=0;j<N;j++){
      const st = perYearStats[j]; if (!st) continue;
      const x = xScale(j) - boxW/2;
      const yq1 = yScale(st.q1), yq3 = yScale(st.q3), ymed = yScale(st.med), ymin = yScale(st.min), ymax = yScale(st.max);
      // Box
      ctx.fillRect(x, yq3, boxW, yq1 - yq3);
      ctx.strokeRect(x, yq3, boxW, yq1 - yq3);
      // Median line
      ctx.beginPath(); ctx.moveTo(x, ymed); ctx.lineTo(x+boxW, ymed); ctx.stroke();
      // Whiskers
      ctx.beginPath(); ctx.moveTo(x+boxW/2, yq3); ctx.lineTo(x+boxW/2, ymax); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(x+boxW/2, yq1); ctx.lineTo(x+boxW/2, ymin); ctx.stroke();
    }
    // Title
    ctx.fillStyle = '#e5e7eb'; ctx.textAlign='left'; ctx.textBaseline='alphabetic'; ctx.font='bold 14px system-ui';
    ctx.fillText('箱ひげ図（年次・系列分布）', 0, -8);
  } else if (view === 'country_pie') {
    // 円グラフ：国別構成比（最新年または選択年）
    if (!gData.countries || !gData.countries.series || gData.countries.series.length === 0) {
      ctx.fillText('国別データがありません', 10, 20); ctx.restore(); return;
    }
    const yearFilter = document.getElementById('yearFilter');
    const selectedYear = yearFilter ? yearFilter.value : '';
    const targetYear = selectedYear || (gData.years && gData.years[gData.years.length - 1]) || '2025';
    
    // 各国の値を収集
    const countryData = [];
    let total = 0;
    for (const countrySeries of gData.countries.series) {
      if (!countrySeries.x || !countrySeries.y) continue;
      const idx = countrySeries.x.indexOf(String(targetYear));
      if (idx >= 0) {
        const val = Number(countrySeries.y[idx] || 0);
        if (val > 0) {  // 正の値のみ
          countryData.push({ label: countrySeries.label, value: val });
          total += val;
        }
      }
    }
    
    if (countryData.length === 0 || total === 0) {
      ctx.fillText('選択年のデータがありません', 10, 20); ctx.restore(); return;
    }
    
    // 値でソート（降順）
    countryData.sort((a, b) => b.value - a.value);
    
    // トップNを取得
    const topN = parseInt(document.getElementById('topN') ? document.getElementById('topN').value : '10', 10);
    const showOthers = document.getElementById('showOthers') ? document.getElementById('showOthers').checked : false;
    
    let displayData = countryData.slice(0, topN);
    
    // 「その他」を集約（円グラフ用）
    if (showOthers && countryData.length > topN) {
      const othersValue = countryData.slice(topN).reduce((sum, item) => sum + item.value, 0);
      if (othersValue > 0) {
        displayData.push({ label: 'その他', value: othersValue });
        total += othersValue;  // 合計に追加
      }
    }
    
    // 円グラフを描画
    const centerX = W / 2;
    const centerY = H / 2;
    const radius = Math.min(W, H) * 0.35;
    
    let startAngle = -Math.PI / 2;  // 12時の位置から開始
    displayData.forEach((item, i) => {
      const angle = (item.value / total) * 2 * Math.PI;
      const endAngle = startAngle + angle;
      
      // 扇形を描画（国名ハッシュで一貫した色）
      ctx.fillStyle = stringToColor(item.label);
      ctx.beginPath();
      ctx.moveTo(centerX, centerY);
      ctx.arc(centerX, centerY, radius, startAngle, endAngle);
      ctx.closePath();
      ctx.fill();
      
      // ラベル（中央角度に配置）
      const midAngle = startAngle + angle / 2;
      const labelX = centerX + Math.cos(midAngle) * radius * 0.7;
      const labelY = centerY + Math.sin(midAngle) * radius * 0.7;
      const percentage = ((item.value / total) * 100).toFixed(1);
      
      ctx.fillStyle = '#fff';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.font = 'bold 12px system-ui';
      if (percentage > 5) {  // 5%以上の場合のみラベル表示
        ctx.fillText(`${percentage}%`, labelX, labelY);
      }
      
      startAngle = endAngle;
    });
    
    // タイトル
    ctx.fillStyle = '#e5e7eb'; ctx.textAlign = 'left'; ctx.textBaseline = 'alphabetic'; ctx.font = 'bold 14px system-ui';
    ctx.fillText(`国別構成比（${targetYear}年・トップ${topN}）`, 0, -8);
    
    // ホバー時のツールチップ処理
    const tip = document.getElementById('status');
    canvas.onmousemove = (ev) => {
      const rect2 = canvas.getBoundingClientRect();
      const mx = (ev.clientX - rect2.left) - margin.l;
      const my = (ev.clientY - rect2.top) - margin.t;
      
      // 円の中心からの距離と角度を計算
      const dx = mx - centerX;
      const dy = my - centerY;
      const dist = Math.sqrt(dx * dx + dy * dy);
      
      if (dist <= radius) {
        let angle = Math.atan2(dy, dx) + Math.PI / 2;  // 12時の位置を0とする
        if (angle < 0) angle += 2 * Math.PI;
        
        // どの扇形にホバーしているかを判定
        let cumAngle = 0;
        for (let i = 0; i < displayData.length; i++) {
          const segAngle = (displayData[i].value / total) * 2 * Math.PI;
          if (angle >= cumAngle && angle < cumAngle + segAngle) {
            const pct = ((displayData[i].value / total) * 100).toFixed(1);
            tip.textContent = `${displayData[i].label}: ${displayData[i].value.toLocaleString()} 億円 (${pct}%)`;
            return;
          }
          cumAngle += segAngle;
        }
      }
      tip.textContent = '';
    };
    
    // 凡例を別途表示（国名ハッシュで一貫した色）
    const legend = document.getElementById('legend');
    legend.innerHTML = '';
    legend.style.maxHeight = '200px';
    legend.style.overflowY = 'auto';
    displayData.forEach((item, i) => {
      const d = document.createElement('div');
      d.className = 'item';
      d.innerHTML = `<span class="swatch" style="background:${stringToColor(item.label)}"></span>${item.label}: ${item.value.toLocaleString()} (${((item.value / total) * 100).toFixed(1)}%)`;
      legend.appendChild(d);
    });
  } else if (view === 'country_bar') {
    // 棒グラフ：国別ランキング（任意年のトップN）
    if (!gData.countries || !gData.countries.series || gData.countries.series.length === 0) {
      ctx.fillText('国別データがありません', 10, 20); ctx.restore(); return;
    }
    const yearFilter = document.getElementById('yearFilter');
    const selectedYear = yearFilter ? yearFilter.value : '';
    const targetYear = selectedYear || (gData.years && gData.years[gData.years.length - 1]) || '2025';
    
    // 各国の値を収集
    const countryData = [];
    for (const countrySeries of gData.countries.series) {
      if (!countrySeries.x || !countrySeries.y) continue;
      const idx = countrySeries.x.indexOf(String(targetYear));
      if (idx >= 0) {
        const val = Number(countrySeries.y[idx] || 0);
        if (val > 0) {  // 正の値のみ
          countryData.push({ label: countrySeries.label, value: val });
        }
      }
    }
    
    if (countryData.length === 0) {
      ctx.fillText('選択年のデータがありません', 10, 20); ctx.restore(); return;
    }
    
    // ソート処理
    const sortBy = document.getElementById('sortBy') ? document.getElementById('sortBy').value : 'value';
    if (sortBy === 'value') {
      countryData.sort((a, b) => b.value - a.value);  // 値（降順）
    } else if (sortBy === 'value_asc') {
      countryData.sort((a, b) => a.value - b.value);  // 値（昇順）
    } else if (sortBy === 'name') {
      countryData.sort((a, b) => a.label.localeCompare(b.label));  // 国名（昇順）
    } else if (sortBy === 'name_desc') {
      countryData.sort((a, b) => b.label.localeCompare(a.label));  // 国名（降順）
    }
    
    // トップNを取得
    const topN = parseInt(document.getElementById('topN') ? document.getElementById('topN').value : '10', 10);
    const displayData = countryData.slice(0, topN);
    
    // スケールタイプ（リニア or ログ）
    const scaleType = document.getElementById('scaleType') ? document.getElementById('scaleType').value : 'linear';
    
    // Y軸のスケール
    const maxVal = Math.max(...displayData.map(d => d.value));
    const minVal = Math.min(...displayData.map(d => d.value).filter(v => v > 0));
    
    let yScale;
    if (scaleType === 'log') {
      // ログスケール
      const logMax = Math.log10(maxVal || 1);
      const logMin = Math.log10(minVal || 0.1);
      yScale = v => {
        if (v <= 0) return H;
        return H - ((Math.log10(v) - logMin) / (logMax - logMin)) * H * 0.9;
      };
    } else {
      // リニアスケール
      yScale = v => H - (v / maxVal) * H * 0.9;
    }
    
    // 横軸の設定
    ctx.strokeStyle = '#1f2937'; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(0, H); ctx.lineTo(W, H); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(0, H); ctx.stroke();
    
    // Y軸の目盛り
    ctx.fillStyle = '#94a3b8'; ctx.textAlign = 'right'; ctx.textBaseline = 'middle';
    const ticks = 5;
    if (scaleType === 'log') {
      // ログスケールの目盛り
      const logMax = Math.log10(maxVal || 1);
      const logMin = Math.log10(minVal || 0.1);
      for (let i = 0; i <= ticks; i++) {
        const logVal = logMin + (i / ticks) * (logMax - logMin);
        const v = Math.pow(10, logVal);
        const y = yScale(v);
        ctx.strokeStyle = '#1f2937'; ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke();
        ctx.fillText(v < 100 ? v.toFixed(1) : v.toFixed(0), -8, y);
      }
    } else {
      // リニアスケールの目盛り
      for (let i = 0; i <= ticks; i++) {
        const v = (i / ticks) * maxVal;
        const y = yScale(v);
        ctx.strokeStyle = '#1f2937'; ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke();
        ctx.fillText(v.toFixed(0), -8, y);
      }
    }
    
    // 棒グラフを描画
    const barW = Math.max(8, Math.min(48, Math.floor(W / (displayData.length * 1.5))));
    const gap = Math.max(8, Math.floor(barW * 0.25));
    ctx.textAlign = 'center'; ctx.textBaseline = 'top';
    
    const barCenters = [];
    displayData.forEach((item, i) => {
      const x = i * (barW + gap);
      const h = H - yScale(item.value);
      ctx.fillStyle = stringToColor(item.label);
      ctx.fillRect(x, H - h, barW, h);
      
      // 値を棒の上に表示
      ctx.fillStyle = '#e5e7eb';
      ctx.font = '10px system-ui';
      ctx.fillText(item.value.toLocaleString(), x + barW / 2, H - h - 4);
      
      // 国名を棒の下に表示（回転）
      ctx.save();
      ctx.translate(x + barW / 2, H + 8);
      ctx.rotate(-Math.PI / 4);
      ctx.fillStyle = '#94a3b8';
      ctx.textAlign = 'right';
      ctx.fillText(item.label.slice(0, 15), 0, 0);
      ctx.restore();
      
      // トレンドライン用の座標を保存
      barCenters.push({x: x + barW / 2, y: H - h});
    });
    
    // トレンドライン（移動平均）
    if (document.getElementById('showTrend') && document.getElementById('showTrend').checked && barCenters.length >= 3) {
      const smoothed = [];
      for (let i=0; i<barCenters.length; i++) {
        if (i === 0) smoothed.push(barCenters[i]);
        else if (i === barCenters.length - 1) smoothed.push(barCenters[i]);
        else {
          const avgY = (barCenters[i-1].y + barCenters[i].y + barCenters[i+1].y) / 3;
          smoothed.push({x: barCenters[i].x, y: avgY});
        }
      }
      ctx.strokeStyle = '#f59e0b'; ctx.lineWidth = 2.5; ctx.setLineDash([5, 5]); ctx.beginPath();
      smoothed.forEach((pt, i) => {
        if (i === 0) ctx.moveTo(pt.x, pt.y);
        else ctx.lineTo(pt.x, pt.y);
      });
      ctx.stroke();
      ctx.setLineDash([]);
    }
    
    // タイトル
    ctx.fillStyle = '#e5e7eb'; ctx.textAlign = 'left'; ctx.textBaseline = 'alphabetic'; ctx.font = 'bold 14px system-ui';
    ctx.fillText(`国別ランキング（${targetYear}年・トップ${topN}）`, 0, -8);
  }
  ctx.restore();
}

function onViewChange() {
  const view = document.getElementById('view').value;
  const isCountryView = view === 'country_pie' || view === 'country_bar';
  const isMultiPanel = view === 'multi_panel';
  const specificControls = document.getElementById('specificControls');
  
  // キャンバスとマルチパネルコンテナの表示切り替え
  document.getElementById('chart').style.display = isMultiPanel ? 'none' : 'block';
  document.getElementById('multiPanelContainer').style.display = isMultiPanel ? 'block' : 'none';
  
  // すべての固有コントロールを非表示
  document.getElementById('topNLabel').style.display = 'none';
  document.getElementById('showOthersLabel').style.display = 'none';
  document.getElementById('sortByLabel').style.display = 'none';
  document.getElementById('scaleLabel').style.display = 'none';
  
  // マルチパネルモードの場合
  if (isMultiPanel) {
    document.getElementById('yearFilterLabel').style.display = 'none';
    document.getElementById('measureLabel').style.display = '';
    document.getElementById('regionFilterLabel').style.display = 'none';
    specificControls.style.display = 'none';
  }
  // 国別ビューの場合
  else if (isCountryView) {
    // 年フィルタの構築
    if (gData && gData.years) {
      const yf = document.getElementById('yearFilter');
      yf.innerHTML = '';
      gData.years.slice().reverse().forEach(y => {
        const o = document.createElement('option');
        o.value = y;
        o.textContent = y;
        yf.appendChild(o);
      });
      document.getElementById('yearFilterLabel').style.display = '';
    }
    
    // 固有コントロールを表示
    specificControls.style.display = 'flex';
    document.getElementById('topNLabel').style.display = '';
    document.getElementById('sortByLabel').style.display = '';
    document.getElementById('scaleLabel').style.display = view === 'country_bar' ? '' : 'none';
    document.getElementById('showOthersLabel').style.display = view === 'country_pie' ? '' : 'none';
    document.getElementById('regionFilterLabel').style.display = 'none';
    document.getElementById('measureLabel').style.display = 'none';
  } else {
    // 通常ビュー
    document.getElementById('yearFilterLabel').style.display = 'none';
    document.getElementById('measureLabel').style.display = '';
    specificControls.style.display = 'none';
    
    // 地域フィルタは時系列ビューで表示
    if (gData && gData.regions && gData.regions.available && gData.regions.available.length > 0) {
      document.getElementById('regionFilterLabel').style.display = (view === 'timeseries' || view === 'yoy_diff') ? '' : 'none';
    }
  }
  
  draw();
}

async function loadExistingSummary() {
  try {
    const res = await fetch('summary.json');
    if (!res.ok) return false;
    const summary = await res.json();
    
    gData = summary;
    document.getElementById('title').textContent = (gData.title || 'MVP Summary');
    const ms = document.getElementById('measure');
    ms.innerHTML='';
    (gData.series||[]).forEach((s,i)=>{ const o=document.createElement('option'); o.value=i; o.textContent=s.label||`series_${i}`; ms.appendChild(o); });
    
    // 地域フィルタの構築
    const regions = (gData.regions && gData.regions.available) || [];
    if (regions.length > 0) {
      const rf = document.getElementById('regionFilter');
      rf.innerHTML = '<option value="">全地域</option>';
      regions.forEach(r => { const o = document.createElement('option'); o.value = r; o.textContent = r; rf.appendChild(o); });
      document.getElementById('regionFilterLabel').style.display = '';
    } else {
      document.getElementById('regionFilterLabel').style.display = 'none';
    }
    
    document.getElementById('controls').style.display = 'flex';
    document.getElementById('chartPanel').style.display = 'block';
    hideUploadPanel();
    const st = document.getElementById('uploadStatus');
    st.textContent = '✓ 既存データを読み込みました';
    setTimeout(() => { st.textContent = ''; }, 3000);
    draw();
    return true;
  } catch (e) {
    return false;
  }
}

window.addEventListener('load', () => {
  const dz = document.getElementById('drop');
  dz.addEventListener('dragover', (e)=>{ e.preventDefault(); dz.style.borderColor = '#60a5fa'; });
  dz.addEventListener('dragleave', (e)=>{ dz.style.borderColor = '#334155'; });
  dz.addEventListener('drop', (e)=>{ e.preventDefault(); dz.style.borderColor = '#334155'; if (e.dataTransfer.files && e.dataTransfer.files[0]) uploadAndAnalyze(e.dataTransfer.files[0]); });
  
  // 全画面ドロップ対応（アップロードパネル非表示時でもファイルを受け付ける）
  document.addEventListener('dragover', (e)=>{ 
    e.preventDefault(); 
    // アップロードパネルが非表示の場合は自動表示
    if (document.getElementById('uploader').style.display === 'none') {
      showUploadPanel();
    }
  });
  document.addEventListener('drop', (e)=>{ 
    e.preventDefault(); 
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      if (document.getElementById('uploader').style.display === 'none') {
        showUploadPanel();
      }
      uploadAndAnalyze(e.dataTransfer.files[0]);
    }
  });
  
  // 既存のsummary.jsonがあれば自動読み込み
  loadExistingSummary();
});
  </script>
</head>
<body>
  <header>
    <div class="title" id="title">InvestViz Dashboard (MVP)</div>
    <div class="actions">
      <label style="display:flex;gap:6px;align-items:center;"><input type="checkbox" id="overlay"> 全系列を重ね描画</label>
      <label style="display:flex;gap:6px;align-items:center;"><input type="checkbox" id="showTrend"> トレンドライン表示</label>
      <button class="btn" onclick="exportMenu()" title="データをエクスポート">💾 エクスポート</button>
      <button class="btn" id="uploadNewBtn" onclick="showUploadPanel()" title="新しいCSVファイルをアップロード">📤 新規CSV</button>
    </div>
  </header>
  <div id="toast" class="toast"></div>
  <main>
    <div id="uploader" class="panel">
      <div class="drop" id="drop">ここに CSV をドラッグ＆ドロップするか、ファイルを選択してください。</div>
      <div style="margin-top:10px; display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
        <input type="file" id="file" accept=".csv" onchange="onSelectFile()" />
        <a id="downloadNormalized" href="#" class="meta" style="text-decoration:none; pointer-events:none;">normalized.csv</a>
        <a id="downloadParseLog" href="#" class="meta" style="text-decoration:none; pointer-events:none;">parse_log.json</a>
        <a id="downloadPivot" href="#" class="meta" style="text-decoration:none; pointer-events:none;">pivot_year_measure.csv</a>
      </div>
      <div class="meta" id="uploadStatus"></div>
    </div>

    <div class="panel" id="chartPanel">
      <div id="controls">
        <!-- 共通コントロール -->
        <div class="control-row common">
          <label>ビュー: 
            <select id="view" onchange="onViewChange()">
              <option value="timeseries">時系列</option>
              <option value="yoy_diff">前年比差分</option>
              <option value="composition">構成比</option>
              <option value="heatmap">ヒートマップ</option>
              <option value="boxplot">箱ひげ図</option>
              <option value="country_pie">国別構成比（円）</option>
              <option value="country_bar">国別ランキング（横棒）</option>
              <option value="multi_panel">マルチパネル（2×2）</option>
            </select>
          </label>
          <label id="measureLabel">系列: 
            <select id="measure" onchange="draw()"></select>
          </label>
          <label id="regionFilterLabel" style="display:none;">地域: 
            <select id="regionFilter" onchange="draw()"></select>
          </label>
          <label id="yearFilterLabel" style="display:none;">年: 
            <select id="yearFilter" onchange="draw()"></select>
          </label>
        </div>
        
        <!-- ビュー固有コントロール -->
        <div class="control-row specific" id="specificControls" style="display:none;">
          <label id="topNLabel" style="display:none;">表示数: 
            <input type="range" id="topN" min="5" max="30" value="10" step="1" onchange="draw(); updateTopNLabel();" style="width:120px;">
            <span id="topNValue">10</span>
          </label>
          <label id="showOthersLabel" style="display:none;">
            <input type="checkbox" id="showOthers" onchange="draw()"> その他を表示
          </label>
          <label id="sortByLabel" style="display:none;">並び順: 
            <select id="sortBy" onchange="draw()">
              <option value="value">値（降順）</option>
              <option value="value_asc">値（昇順）</option>
              <option value="name">国名 A→Z</option>
              <option value="name_desc">国名 Z→A</option>
            </select>
          </label>
          <label id="scaleLabel" style="display:none;">スケール: 
            <select id="scaleType" onchange="draw()">
              <option value="linear">リニア</option>
              <option value="log">ログ</option>
            </select>
          </label>
        </div>
        
        <div class="control-row">
          <button class="btn" id="exportBtn" onclick="exportCurrentView()" title="現在のビュー（フィルタ適用済み）をCSVでダウンロード">📥 CSVエクスポート</button>
        </div>
      </div>
      <canvas id="chart"></canvas>
      <div id="multiPanelContainer" style="display:none;">
        <div class="multi-panel-grid">
          <div class="panel-item">
            <div class="panel-title">時系列推移</div>
            <canvas id="chart1"></canvas>
          </div>
          <div class="panel-item">
            <div class="panel-title">前年比差分（YoY）</div>
            <canvas id="chart2"></canvas>
          </div>
          <div class="panel-item">
            <div class="panel-title">国別ランキング（Top 5）</div>
            <canvas id="chart3"></canvas>
          </div>
          <div class="panel-item">
            <div class="panel-title">構成比</div>
            <canvas id="chart4"></canvas>
          </div>
        </div>
      </div>
      <div class="legend" id="legend"></div>
      <div class="meta" id="status">CSV をアップロードすると可視化が表示されます。</div>
    </div>
  </main>
  <script>
    function exportCurrentView() {
      if (!gData) {
        alert('データがありません。CSVファイルをアップロードしてください。');
        return;
      }
      
      const view = document.getElementById('view').value;
      const regionFilter = document.getElementById('regionFilter');
      const region = regionFilter && regionFilter.value ? regionFilter.value : '';
      
      // クエリパラメータを構築
      const params = new URLSearchParams();
      params.append('view', view);
      if (region) {
        params.append('region', region);
      }
      
      // 国別ビューの場合
      if (view === 'country_pie' || view === 'country_bar') {
        const yearFilter = document.getElementById('yearFilter');
        const year = yearFilter && yearFilter.value ? yearFilter.value : '';
        if (year) {
          params.append('year', year);
        }
        const topN = document.getElementById('topN') ? document.getElementById('topN').value : '10';
        params.append('top_n', topN);
        
        // ソート情報（棒グラフ用）
        if (view === 'country_bar') {
          const sortBy = document.getElementById('sortBy') ? document.getElementById('sortBy').value : 'value';
          params.append('sort_by', sortBy);
        }
      } else {
        // 年範囲（現在のデータから取得）
        if (gData.years && gData.years.length > 0) {
          params.append('year_from', gData.years[0]);
          params.append('year_to', gData.years[gData.years.length - 1]);
        }
      }
      
      // セッションIDを追加（存在する場合）
      if (gSessionId) {
        params.append('sid', gSessionId);
      }
      
      // エクスポートURLを生成
      const url = `/api/export?${params.toString()}`;
      
      // ダウンロードを開始
      const a = document.createElement('a');
      a.href = url;
      a.download = '';  // サーバーが指定したファイル名を使用
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setTimeout(() => showToast('エクスポート完了！', 2000), 1000);
    }
    
    function exportNormalized() {
      if (!gSessionId) {
        alert('セッションIDが見つかりません。データを再アップロードしてください。');
        return;
      }
      showToast('正規化データをエクスポート中...', 2000);
      const url = `/uploads/${gSessionId}/normalized.csv`;
      const a = document.createElement('a');
      a.href = url;
      a.download = 'normalized.csv';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setTimeout(() => showToast('エクスポート完了！', 2000), 1000);
    }
    
    function exportPivot() {
      if (!gSessionId) {
        alert('セッションIDが見つかりません。データを再アップロードしてください。');
        return;
      }
      showToast('ピボットデータをエクスポート中...', 2000);
      const url = `/uploads/${gSessionId}/pivot_year_measure.csv`;
      const a = document.createElement('a');
      a.href = url;
      a.download = 'pivot_year_measure.csv';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setTimeout(() => showToast('エクスポート完了！', 2000), 1000);
    }
    
    function exportImage() {
      showToast('画像をエクスポート中...', 2000);
      const canvas = document.getElementById('chart');
      canvas.toBlob((blob) => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `chart_${Date.now()}.png`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        showToast('画像エクスポート完了！', 2000);
      }, 'image/png');
    }
    
    // エクスポートメニュー
    function exportMenu() {
      if (!gData) {
        alert('データがありません。CSVファイルをアップロードしてください。');
        return;
      }
      
      const choice = prompt('エクスポート種類を選択してください:\n1: 現在のビュー (CSV)\n2: 正規化データ (normalized.csv)\n3: ピボットデータ (pivot_year_measure.csv)\n4: 画像 (PNG)', '1');
      if (!choice) return;
      
      if (choice === '1') {
        showToast('現在のビューをエクスポート中...', 2000);
        exportCurrentView();
      } else if (choice === '2') {
        exportNormalized();
      } else if (choice === '3') {
        exportPivot();
      } else if (choice === '4') {
        exportImage();
      } else {
        alert('無効な選択です');
      }
    }
    
    document.getElementById('overlay').addEventListener('change', (e)=>{ gOverlay = e.target.checked; draw(); const legend = document.getElementById('legend'); legend.innerHTML = ''; if (gOverlay) { (gData.series||[]).forEach((s,i)=>{ const d=document.createElement('div'); d.className='item'; d.innerHTML=`<span class="swatch" style="background:${gColors[i%gColors.length]}"></span>${s.label}`; legend.appendChild(d); }); }});
    document.getElementById('showTrend').addEventListener('change', ()=> draw());
    window.addEventListener('resize', ()=> draw());
  </script>
</body>
</html>
"""


def write_index_html(build_dir: str) -> str:
    os.makedirs(build_dir, exist_ok=True)
    path = os.path.join(build_dir, "index.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(INDEX_HTML)
    return path


class AppHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        # エクスポートAPIの処理
        if self.path.startswith("/api/export"):
            self.handle_export()
            return
        # 通常のファイル提供
        super().do_GET()
    
    def handle_export(self):
        """フィルタ適用済みCSVエクスポート"""
        try:
            from urllib.parse import urlparse, parse_qs
            import csv as csv_module
            from io import StringIO, BytesIO
            
            # クエリパラメータを解析
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            
            # パラメータを取得
            region = params.get('region', [''])[0]
            year_from = params.get('year_from', [''])[0]
            year_to = params.get('year_to', [''])[0]
            year = params.get('year', [''])[0]  # 単年指定（国別ビュー用）
            view = params.get('view', ['timeseries'])[0]
            sid = params.get('sid', [''])[0]  # セッションID
            top_n = params.get('top_n', ['10'])[0]  # トップN
            sort_by = params.get('sort_by', ['value'])[0]  # ソート順
            
            # normalized.csvを読み込み（セッション対応）
            if sid:
                # セッションIDが指定されている場合は uploads/<sid>/normalized.csv を使用
                norm_path = os.path.join('uploads', sid, 'normalized.csv')
            else:
                # セッションIDがない場合は既定パス（後方互換性）
                norm_path = 'normalized.csv'
                if not os.path.exists(norm_path):
                    norm_path = 'build/normalized.csv'
            
            if not os.path.exists(norm_path):
                self.send_error(404, "No data available. Please upload a file first.")
                return
            
            # ビュー種別に応じた処理
            if view in ['country_pie', 'country_bar']:
                # 国別ビュー用の特別処理（集計済みデータを生成）
                from mof_investviz.normalize import get_region_level
                
                # 年フィルタ
                target_year = year or year_to or None
                
                # データを集計
                country_data = {}
                with open(norm_path, 'r', encoding='utf-8') as f:
                    reader = csv_module.DictReader(f)
                    for row in reader:
                        segment_region = row.get('segment_region', '')
                        if not segment_region:
                            continue
                        
                        # 国レベルのみを対象
                        level = get_region_level(segment_region)
                        if level != 'country':
                            continue
                        
                        # 年フィルタ
                        if target_year:
                            try:
                                row_year = int(row.get('year', 0) or 0)
                                if row_year != int(target_year):
                                    continue
                            except (ValueError, TypeError):
                                continue
                        
                        # 集計
                        val = float(row.get('value_100m_yen', 0) or 0)
                        if segment_region not in country_data:
                            country_data[segment_region] = 0
                        country_data[segment_region] += val
                
                # ソート
                items = list(country_data.items())
                if sort_by == 'value':
                    items.sort(key=lambda x: x[1], reverse=True)
                elif sort_by == 'value_asc':
                    items.sort(key=lambda x: x[1])
                elif sort_by == 'name':
                    items.sort(key=lambda x: x[0])
                elif sort_by == 'name_desc':
                    items.sort(key=lambda x: x[0], reverse=True)
                
                # トップN
                try:
                    n = int(top_n)
                    items = items[:n]
                except (ValueError, TypeError):
                    pass
                
                # CSV用の行を生成
                filtered_rows = [
                    {'country': country, 'value_100m_yen': value, 'rank': i+1}
                    for i, (country, value) in enumerate(items)
                ]
            else:
                # 通常のビュー用のフィルタ処理
                filtered_rows = []
                with open(norm_path, 'r', encoding='utf-8') as f:
                    reader = csv_module.DictReader(f)
                    for row in reader:
                        # 地域フィルタ
                        if region and row.get('segment_region', '') != region:
                            continue
                        
                        # 年範囲フィルタ
                        if year_from or year_to:
                            try:
                                row_year = int(row.get('year', 0) or 0)
                                if year_from and row_year < int(year_from):
                                    continue
                                if year_to and row_year > int(year_to):
                                    continue
                            except (ValueError, TypeError):
                                continue
                        
                        filtered_rows.append(row)
            
            if not filtered_rows:
                self.send_error(404, "No data matches the specified filters.")
                return
            
            # CSVに書き出し（UTF-8 BOM付き + メタデータ）
            import datetime
            output = BytesIO()
            output.write('\ufeff'.encode('utf-8'))  # BOMを追加
            
            # メタデータヘッダー
            text_output = StringIO()
            text_output.write(f'# InvestViz CSV Export\n')
            text_output.write(f'# Generated: {datetime.datetime.now().isoformat()}\n')
            text_output.write(f'# View: {view}\n')
            if view in ['country_pie', 'country_bar']:
                text_output.write(f'# Year: {year or "latest"}\n')
                text_output.write(f'# Top N: {top_n}\n')
                text_output.write(f'# Sort: {sort_by}\n')
            else:
                if region:
                    text_output.write(f'# Region: {region}\n')
                if year_from:
                    text_output.write(f'# Year From: {year_from}\n')
                if year_to:
                    text_output.write(f'# Year To: {year_to}\n')
            text_output.write(f'# Rows: {len(filtered_rows)}\n')
            text_output.write('#\n')
            
            # データ
            if filtered_rows:
                writer = csv_module.DictWriter(text_output, fieldnames=filtered_rows[0].keys())
                writer.writeheader()
                writer.writerows(filtered_rows)
            output.write(text_output.getvalue().encode('utf-8'))
            
            # ファイル名を生成（URLエンコード）
            import datetime
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            filename_parts = ['investviz', view]
            
            if view in ['country_pie', 'country_bar']:
                # 国別ビュー
                if year:
                    filename_parts.append(f'year{year}')
                filename_parts.append(f'top{top_n}')
                if sort_by != 'value':
                    filename_parts.append(sort_by)
            else:
                # 通常ビュー
                if region:
                    # 日本語の地域名をASCII互換に変換
                    import unicodedata
                    region_ascii = region.replace(' ', '_').replace('/', '_')
                    filename_parts.append(region_ascii)
                if year_from or year_to:
                    year_range = f"{year_from or 'start'}-{year_to or 'end'}"
                    filename_parts.append(year_range)
            
            filename_parts.append(timestamp)
            filename = '_'.join(filename_parts) + '.csv'
            
            # レスポンスを返す
            body = output.getvalue()
            self.send_response(200)
            self.send_header('Content-Type', 'text/csv; charset=utf-8')
            self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            msg = json.dumps({"error": str(e)}).encode('utf-8')
            self.send_response(500)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(msg)))
            self.end_headers()
            self.wfile.write(msg)
    
    def do_POST(self):
        if self.path != "/api/upload":
            self.send_error(404, "Not Found")
            return
        try:
            ctype, pdict = cgi.parse_header(self.headers.get('content-type', ''))
            if ctype != 'multipart/form-data':
                self.send_error(400, "Expected multipart/form-data")
                return
            pdict['boundary'] = bytes(pdict['boundary'], 'utf-8')
            pdict['CONTENT-LENGTH'] = int(self.headers.get('content-length', '0'))
            form = cgi.FieldStorage(fp=self.rfile, headers=self.headers, environ={'REQUEST_METHOD':'POST', 'CONTENT_TYPE': self.headers.get('content-type')})
            if 'file' not in form:
                self.send_error(400, "file field missing")
                return
            item = form['file']
            data = item.file.read() if hasattr(item, 'file') else item.value
            sid = str(uuid.uuid4())
            up_dir = os.path.join('uploads', sid)
            os.makedirs(up_dir, exist_ok=True)
            in_path = os.path.join(up_dir, item.filename or 'uploaded.csv')
            with open(in_path, 'wb') as f:
                f.write(data)

            res = normalize_file(in_path)
            write_csv(os.path.join(up_dir, 'normalized.csv'), res.rows, SCHEMA_HEADERS)
            # Build a simple pivot: year x measure (sum of values)
            # Collect years and measures
            pivot_map = {}
            measures = set()
            for r in res.rows:
                y = r.get('year')
                if y is None:
                    continue
                m = str(r.get('measure'))
                v = float(r.get('value_100m_yen') or 0.0)
                measures.add(m)
                d = pivot_map.setdefault(int(y), {})
                d[m] = d.get(m, 0.0) + v
            measures_sorted = sorted(measures)
            pivot_headers = ['year'] + measures_sorted
            pivot_rows = []
            for y in sorted(pivot_map.keys()):
                row = {'year': y}
                row.update({m: pivot_map[y].get(m, 0.0) for m in measures_sorted})
                pivot_rows.append(row)
            write_csv(os.path.join(up_dir, 'pivot_year_measure.csv'), pivot_rows, pivot_headers)
            summary = build_summary_multi_measure(res.rows)
            with open(os.path.join(up_dir, 'summary.json'), 'w', encoding='utf-8') as f:
                json.dump(summary, f, ensure_ascii=False, indent=2)
            parse_log = {"pipeline": "upload", "inputs": [{
                "path": res.meta.get("path"),
                "encoding": res.meta.get("encoding"),
                "delimiter": res.meta.get("delimiter"),
                "header_rows": res.meta.get("header_rows"),
                "headers": res.headers,
                "unit_detected": res.meta.get("unit_detected"),
                "scale_factor": res.meta.get("scale_factor"),
                "side": res.meta.get("side"),
                "metric": res.meta.get("metric"),
                "stats": res.stats,
            }], **schema_meta()}
            with open(os.path.join(up_dir, 'parse_log.json'), 'w', encoding='utf-8') as f:
                json.dump(parse_log, f, ensure_ascii=False, indent=2)
            resp = {"summary": summary, "links": {"normalized_csv": f"/uploads/{sid}/normalized.csv", "parse_log": f"/uploads/{sid}/parse_log.json", "pivot_csv": f"/uploads/{sid}/pivot_year_measure.csv"}}
            body = json.dumps(resp).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            msg = {"error": str(e)}
            body = json.dumps(msg).encode('utf-8')
            self.send_response(500)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)


def serve_build_dir(build_dir: str, host: str = "0.0.0.0", port: int = 8000) -> None:
    os.chdir(build_dir)
    class ThreadingHTTPServer(socketserver.ThreadingTCPServer):
        allow_reuse_address = True
    with ThreadingHTTPServer((host, port), AppHandler) as httpd:
        print(f"Serving {build_dir} at http://{host}:{port}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
