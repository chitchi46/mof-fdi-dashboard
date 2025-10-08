from __future__ import annotations

import http.server
import os
import socketserver


INDEX_HTML = """<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>InvestViz Dashboard (MVP)</title>
  <style>
    body { font-family: system-ui, -apple-system, Segoe UI, Roboto, 'Noto Sans JP', sans-serif; margin: 0; }
    header { padding: 12px 16px; background: #0f172a; color: #fff; }
    main { padding: 16px; }
    #controls { margin-bottom: 12px; display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
    select { padding: 4px 8px; border: 1px solid #d1d5db; border-radius: 4px; }
    #regionFilter { min-width: 200px; max-width: 300px; }
    #chart { width: 100%; height: 420px; border: 1px solid #e5e7eb; }
    .meta { color: #475569; font-size: 12px; margin-top: 8px; }
    .filter-group { display: flex; align-items: center; gap: 4px; }
    label { font-size: 14px; color: #374151; }
  </style>
  <script>
let gData = null;

async function loadSummary() {
  const res = await fetch('summary.json');
  if (!res.ok) throw new Error('summary.json が見つかりません');
  const data = await res.json();
  gData = data;
  document.getElementById('title').textContent = data.title || 'InvestViz Dashboard (MVP)';
  
  // 系列セレクト
  const measureSelect = document.getElementById('measure');
  measureSelect.innerHTML = '';
  (data.series || []).forEach((s, i) => {
    const opt = document.createElement('option');
    opt.value = i; opt.textContent = s.label || `series_${i}`;
    measureSelect.appendChild(opt);
  });
  
  // 地域フィルタの構築
  const regionFilter = document.getElementById('regionFilter');
  const regions = (data.regions && data.regions.available) || [];
  if (regions.length > 0) {
    regionFilter.innerHTML = '<option value="">全地域</option>';
    regions.forEach(r => {
      const opt = document.createElement('option');
      opt.value = r;
      opt.textContent = r;
      regionFilter.appendChild(opt);
    });
    document.getElementById('regionFilterGroup').style.display = 'flex';
  } else {
    document.getElementById('regionFilterGroup').style.display = 'none';
  }
  
  draw();
}

function draw(){
  const canvas = document.getElementById('chart');
  const ctx = canvas.getContext('2d');
  const rect = canvas.getBoundingClientRect();
  canvas.width = rect.width * devicePixelRatio;
  canvas.height = rect.height * devicePixelRatio;
  ctx.setTransform(devicePixelRatio,0,0,devicePixelRatio,0,0);
  ctx.clearRect(0,0,rect.width,rect.height);

  const margin = {l: 48, r: 16, t: 24, b: 48};
  const W = rect.width - margin.l - margin.r;
  const H = rect.height - margin.t - margin.b;
  ctx.save();
  ctx.translate(margin.l, margin.t);

  const view = document.getElementById('view').value;
  const selectedRegion = document.getElementById('regionFilter').value;
  
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
    const xs = series.x;
    let ys = series.y.map(Number);
    if (view === 'yoy_diff') {
      const diff = [];
      for (let i=0; i<ys.length; i++) diff.push(i ? ys[i]-ys[i-1] : 0);
      ys = diff;
    }
    if (xs.length === 0) { ctx.fillText('チE�Eタがありません', 10, 20); ctx.restore(); return; }
    const minY = Math.min(...ys);
    const maxY = Math.max(...ys);
    const padY = (maxY - minY) * 0.1 || 1;
    const y0 = minY - padY;
    const y1 = maxY + padY;
    const xScale = i => (i/(xs.length-1)) * W;
    const yScale = v => H - ((v - y0)/(y1 - y0)) * H;
    // Axes
    ctx.strokeStyle = '#94a3b8'; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(0,H); ctx.lineTo(W,H); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(0,0); ctx.lineTo(0,H); ctx.stroke();
    // Ticks (Y)
    ctx.fillStyle = '#475569'; ctx.textAlign = 'right'; ctx.textBaseline = 'middle';
    const ticks = 5;
    for (let i=0;i<=ticks;i++){
      const v = y0 + (i/ticks)*(y1-y0);
      const y = yScale(v);
      ctx.strokeStyle = '#e2e8f0'; ctx.beginPath(); ctx.moveTo(0,y); ctx.lineTo(W,y); ctx.stroke();
      ctx.fillText(v.toFixed(0), -6, y);
    }
    // X labels
    ctx.textAlign = 'center'; ctx.textBaseline = 'top'; ctx.fillStyle = '#475569';
    const step = Math.ceil(xs.length / 8);
    for (let i=0;i<xs.length;i+=step){ ctx.fillText(String(xs[i]), xScale(i), H+8); }
    // Line
    ctx.strokeStyle = '#2563eb'; ctx.lineWidth = 2; ctx.beginPath();
    for (let i=0;i<ys.length;i++){ const x = xScale(i), y = yScale(ys[i]); if (i===0) ctx.moveTo(x,y); else ctx.lineTo(x,y);} ctx.stroke();
    // Title
    ctx.fillStyle = '#0f172a'; ctx.textAlign = 'left'; ctx.textBaseline = 'alphabetic'; ctx.font = 'bold 14px system-ui';
    ctx.fillText(series.label + (view==='yoy_diff'?'�E�前年比差刁E��E:''), 0, -6);
  } else if (view === 'composition') {
    // 地域別構成比か通常の構成比かを判定
    let comp, labels, share;
    if (selectedRegion) {
      // 地域が選択されている場合は通常の時系列データを表示（構成比は意味が薄い）
      ctx.fillText('地域選択時は時系列ビューを使用してください', 10, 20); 
      ctx.restore(); 
      return;
    } else {
      comp = gData.composition || {labels:[], share:[]};
      labels = comp.labels || [];
      share = (comp.share || []).map(Number);
    }
    if (labels.length === 0) { ctx.fillText('構成比データがありません', 10, 20); ctx.restore(); return; }
    // Bar chart
    const barW = Math.max(8, Math.min(48, Math.floor(W / (labels.length*1.5))));
    const gap = Math.max(8, Math.floor(barW * 0.25));
    ctx.textAlign = 'center'; ctx.textBaseline = 'top';
    for (let i=0; i<labels.length; i++){
      const x = i * (barW + gap);
      const h = Math.round((share[i]) * H);
      ctx.fillStyle = '#60a5fa'; ctx.fillRect(x, H - h, barW, h);
      ctx.fillStyle = '#475569'; ctx.fillText(labels[i].slice(0,12), x + barW/2, H + 8);
    }
    ctx.fillStyle = '#0f172a'; ctx.textAlign = 'left'; ctx.textBaseline = 'alphabetic'; ctx.font = 'bold 14px system-ui';
    ctx.fillText('構�E比！E + (comp.year || '最新年') + '�E�E, 0, -6);
  }
  ctx.restore();
}

window.addEventListener('load', () => { loadSummary().catch(err => { document.getElementById('status').textContent = err.message; }); });
  </script>
</head>
<body>
  <header><strong id="title">InvestViz Dashboard (MVP)</strong></header>
  <main>
    <div id="controls">
      <div class="filter-group">
        <label>ビュー: 
          <select id="view" onchange="draw()">
            <option value="timeseries">時系列</option>
            <option value="yoy_diff">前年比差分</option>
            <option value="composition">構成比</option>
          </select>
        </label>
      </div>
      <div class="filter-group">
        <label>系列: 
          <select id="measure" onchange="draw()"></select>
        </label>
      </div>
      <div class="filter-group" id="regionFilterGroup" style="display: none;">
        <label>地域: 
          <select id="regionFilter" onchange="draw()"></select>
        </label>
      </div>
    </div>
    <canvas id="chart"></canvas>
    <div class="meta" id="status">summary.json を読み込み、単一または複数系列のグラフを表示します。</div>
  </main>
</body>
</html>
"""


def write_index_html(build_dir: str) -> str:
    os.makedirs(build_dir, exist_ok=True)
    path = os.path.join(build_dir, "index.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(INDEX_HTML)
    return path


def serve_build_dir(build_dir: str, host: str = "127.0.0.1", port: int = 8000) -> None:
    os.chdir(build_dir)
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer((host, port), handler) as httpd:
        print(f"Serving {build_dir} at http://{host}:{port}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass

