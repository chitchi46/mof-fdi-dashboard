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
    #controls { display:none; flex-wrap:wrap; gap:12px; margin-bottom:12px; align-items:center; }
    select, button, input[type=checkbox] { background:#0f172a; color:#e5e7eb; border:1px solid #334155; border-radius:6px; padding:6px 8px; }
    #chartPanel { display:none; }
    #chart { width:100%; height:420px; border:1px solid #334155; border-radius:8px; background:#0b1220; }
    .meta { color: var(--muted); font-size: 12px; margin-top: 8px; }
    .legend { display:flex; flex-wrap:wrap; gap:12px; margin:8px 0; }
    .legend .item { display:flex; align-items:center; gap:6px; color: var(--muted); }
    .swatch { display:inline-block; width:12px; height:12px; border-radius:2px; }
    .drop { border:1px dashed #334155; border-radius:8px; padding:18px; text-align:center; color:var(--muted); }
  </style>
  <script>
let gData = null;
let gColors = ['#60a5fa','#f472b6','#f59e0b','#34d399','#a78bfa','#f43f5e','#22d3ee'];
let gOverlay = false;
let gSessionId = null;  // 現在のセッションID

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

function draw(){
  if (!gData) return;
  const canvas = document.getElementById('chart');
  const ctx = canvas.getContext('2d');
  const rect = canvas.getBoundingClientRect();
  canvas.width = rect.width * devicePixelRatio;
  canvas.height = rect.height * devicePixelRatio;
  ctx.setTransform(devicePixelRatio,0,0,devicePixelRatio,0,0);
  ctx.clearRect(0,0,rect.width,rect.height);

  const margin = {l: 56, r: 16, t: 30, b: 56};
  const W = rect.width - margin.l - margin.r;
  const H = rect.height - margin.t - margin.b;
  ctx.save();
  ctx.translate(margin.l, margin.t);

  const view = document.getElementById('view').value;
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
    ctx.strokeStyle = '#1f2937'; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(0,H); ctx.lineTo(W,H); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(0,0); ctx.lineTo(0,H); ctx.stroke();
    // Ticks (Y)
    ctx.fillStyle = '#94a3b8'; ctx.textAlign = 'right'; ctx.textBaseline = 'middle';
    const ticks = 5;
    for (let i=0;i<=ticks;i++){
      const v = y0 + (i/ticks)*(y1-y0);
      const y = yScale(v);
      ctx.strokeStyle = '#1f2937'; ctx.beginPath(); ctx.moveTo(0,y); ctx.lineTo(W,y); ctx.stroke();
      ctx.fillText(v.toFixed(0), -8, y);
    }
    // X labels
    ctx.textAlign = 'center'; ctx.textBaseline = 'top'; ctx.fillStyle = '#94a3b8';
    const step = Math.ceil(xs.length / 8);
    for (let i=0;i<xs.length;i+=step){ ctx.fillText(String(xs[i]), xScale(i), H+10); }
    // Lines
    function drawLine(lineXs, lineYs, color){
      ctx.strokeStyle = color; ctx.lineWidth = 2; ctx.beginPath();
      for (let i=0;i<lineYs.length;i++){ const x = xScale(i), y = yScale(lineYs[i]); if (i===0) ctx.moveTo(x,y); else ctx.lineTo(x,y);} ctx.stroke();
    }
    if (gOverlay) {
      (gData.series||[]).forEach((s,i)=>{ drawLine(s.x, s.y.map(Number), gColors[i%gColors.length]); });
    } else {
      drawLine(xs, ys, gColors[0]);
    }
    // Title
    ctx.fillStyle = '#e5e7eb'; ctx.textAlign = 'left'; ctx.textBaseline = 'alphabetic'; ctx.font = 'bold 14px system-ui';
    const ttl = gOverlay ? '上位系列（重ね描画）' : (series.label + (view==='yoy_diff'?'（前年比差分）':''));
    ctx.fillText(ttl, 0, -8);
    // Hover tooltips
    const tip = document.getElementById('status');
    canvas.onmousemove = (ev)=>{
      const rect2 = canvas.getBoundingClientRect();
      const mx = (ev.clientX - rect2.left) - margin.l;
      const my = (ev.clientY - rect2.top) - margin.t;
      if (mx<0 || mx>W || my<0 || my>H) { tip.textContent = ''; return; }
      const idx = Math.round((mx/W) * (xs.length-1));
      let txt = '';
      if (gOverlay){
        const parts = (gData.series||[]).map((s,i)=>`${s.label}: ${Number(s.y[idx]||0).toLocaleString()}`);
        txt = `${xs[idx]} — ${parts.join(' / ')}`;
      } else {
        txt = `${xs[idx]} — ${Number(ys[idx]||0).toLocaleString()} (${series.label})`;
      }
      tip.textContent = txt;
    };
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
    const displayData = countryData.slice(0, topN);
    
    // 円グラフを描画
    const centerX = W / 2;
    const centerY = H / 2;
    const radius = Math.min(W, H) * 0.35;
    
    let startAngle = -Math.PI / 2;  // 12時の位置から開始
    displayData.forEach((item, i) => {
      const angle = (item.value / total) * 2 * Math.PI;
      const endAngle = startAngle + angle;
      
      // 扇形を描画
      ctx.fillStyle = gColors[i % gColors.length];
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
    
    // 凡例を別途表示
    const legend = document.getElementById('legend');
    legend.innerHTML = '';
    displayData.forEach((item, i) => {
      const d = document.createElement('div');
      d.className = 'item';
      d.innerHTML = `<span class="swatch" style="background:${gColors[i % gColors.length]}"></span>${item.label}: ${item.value.toLocaleString()} (${((item.value / total) * 100).toFixed(1)}%)`;
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
    
    // 値でソート（降順）
    countryData.sort((a, b) => b.value - a.value);
    
    // トップNを取得
    const topN = parseInt(document.getElementById('topN') ? document.getElementById('topN').value : '10', 10);
    const displayData = countryData.slice(0, topN);
    
    // Y軸のスケール
    const maxVal = Math.max(...displayData.map(d => d.value));
    const yScale = v => H - (v / maxVal) * H * 0.9;
    
    // 横軸の設定
    ctx.strokeStyle = '#1f2937'; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(0, H); ctx.lineTo(W, H); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(0, H); ctx.stroke();
    
    // Y軸の目盛り
    ctx.fillStyle = '#94a3b8'; ctx.textAlign = 'right'; ctx.textBaseline = 'middle';
    const ticks = 5;
    for (let i = 0; i <= ticks; i++) {
      const v = (i / ticks) * maxVal;
      const y = yScale(v);
      ctx.strokeStyle = '#1f2937'; ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke();
      ctx.fillText(v.toFixed(0), -8, y);
    }
    
    // 棒グラフを描画
    const barW = Math.max(8, Math.min(48, Math.floor(W / (displayData.length * 1.5))));
    const gap = Math.max(8, Math.floor(barW * 0.25));
    ctx.textAlign = 'center'; ctx.textBaseline = 'top';
    
    displayData.forEach((item, i) => {
      const x = i * (barW + gap);
      const h = H - yScale(item.value);
      ctx.fillStyle = gColors[i % gColors.length];
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
    });
    
    // タイトル
    ctx.fillStyle = '#e5e7eb'; ctx.textAlign = 'left'; ctx.textBaseline = 'alphabetic'; ctx.font = 'bold 14px system-ui';
    ctx.fillText(`国別ランキング（${targetYear}年・トップ${topN}）`, 0, -8);
  }
  ctx.restore();
}

function onViewChange() {
  const view = document.getElementById('view').value;
  const isCountryView = view === 'country_pie' || view === 'country_bar';
  
  // 国別ビューの場合、年フィルタとトップN選択を表示
  if (isCountryView) {
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
    document.getElementById('topNLabel').style.display = '';
    document.getElementById('regionFilterLabel').style.display = 'none';  // 地域フィルタは非表示
  } else {
    document.getElementById('yearFilterLabel').style.display = 'none';
    document.getElementById('topNLabel').style.display = 'none';
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
      <button class="btn" id="uploadNewBtn" onclick="showUploadPanel()" title="新しいCSVファイルをアップロード">📤 新規CSV</button>
    </div>
  </header>
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
        <label>ビュー: 
          <select id="view" onchange="onViewChange()">
            <option value="timeseries">時系列</option>
            <option value="yoy_diff">前年比差分</option>
            <option value="composition">構成比</option>
            <option value="heatmap">ヒートマップ</option>
            <option value="boxplot">箱ひげ図</option>
            <option value="country_pie">国別構成比（円）</option>
            <option value="country_bar">国別ランキング（棒）</option>
          </select>
        </label>
        <label>系列: 
          <select id="measure" onchange="draw()"></select>
        </label>
        <label id="regionFilterLabel" style="display:none;">地域: 
          <select id="regionFilter" onchange="draw()"></select>
        </label>
        <label id="yearFilterLabel" style="display:none;">年: 
          <select id="yearFilter" onchange="draw()"></select>
        </label>
        <label id="topNLabel" style="display:none;">表示数: 
          <select id="topN" onchange="draw()">
            <option value="5">トップ5</option>
            <option value="10" selected>トップ10</option>
            <option value="15">トップ15</option>
            <option value="20">トップ20</option>
          </select>
        </label>
        <button class="btn" id="exportBtn" onclick="exportCurrentView()" title="現在のビュー（フィルタ適用済み）をCSVでダウンロード">📥 CSVエクスポート</button>
      </div>
      <canvas id="chart"></canvas>
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
      
      // 年範囲（現在のデータから取得）
      if (gData.years && gData.years.length > 0) {
        params.append('year_from', gData.years[0]);
        params.append('year_to', gData.years[gData.years.length - 1]);
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
      
      // ステータス表示
      const st = document.getElementById('status');
      const prevText = st.textContent;
      st.textContent = '✓ CSVエクスポートを開始しました...';
      setTimeout(() => { st.textContent = prevText; }, 3000);
    }
    
    document.getElementById('overlay').addEventListener('change', (e)=>{ gOverlay = e.target.checked; draw(); const legend = document.getElementById('legend'); legend.innerHTML = ''; if (gOverlay) { (gData.series||[]).forEach((s,i)=>{ const d=document.createElement('div'); d.className='item'; d.innerHTML=`<span class="swatch" style="background:${gColors[i%gColors.length]}"></span>${s.label}`; legend.appendChild(d); }); }});
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
            view = params.get('view', ['timeseries'])[0]
            sid = params.get('sid', [''])[0]  # セッションID
            
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
            
            # CSVを読み込んでフィルタ適用
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
                            year = int(row.get('year', 0) or 0)
                            if year_from and year < int(year_from):
                                continue
                            if year_to and year > int(year_to):
                                continue
                        except (ValueError, TypeError):
                            continue
                    
                    filtered_rows.append(row)
            
            if not filtered_rows:
                self.send_error(404, "No data matches the specified filters.")
                return
            
            # CSVに書き出し（UTF-8 BOM付き）
            output = BytesIO()
            output.write('\ufeff'.encode('utf-8'))  # BOMを追加
            text_output = StringIO()
            if filtered_rows:
                writer = csv_module.DictWriter(text_output, fieldnames=filtered_rows[0].keys())
                writer.writeheader()
                writer.writerows(filtered_rows)
            output.write(text_output.getvalue().encode('utf-8'))
            
            # ファイル名を生成（URLエンコード）
            filename_parts = ['investviz', view]
            if region:
                # 日本語の地域名をASCII互換に変換
                import unicodedata
                region_ascii = region.replace(' ', '_').replace('/', '_')
                filename_parts.append(region_ascii)
            if year_from or year_to:
                year_range = f"{year_from or 'start'}-{year_to or 'end'}"
                filename_parts.append(year_range)
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
