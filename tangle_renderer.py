"""
tangle_renderer.py
------------------
Tangle Renderer module (Section III of BTxC Forensix).

Reads results.json and emits a single self-contained HTML file with an
interactive D3.js GUI:

  * Transaction View — DAG, flag-type filter checkboxes, address search,
                       hover tooltips, neighbor highlight, zoom-to-fit,
                       CSV export of filtered set.
  * Cluster View    — clusters as nodes, fund-flow edges, address search,
                       hover tooltips, neighbor highlight, zoom-to-fit.
  * Dashboard       — flag distribution donut, cluster-size histogram,
                       transaction timeline, top suspicious table.
"""

from __future__ import annotations

import argparse
import json
import os


def build_html(payload: dict) -> str:
    data_json = json.dumps(payload, separators=(",", ":"))
    n_tx  = len(payload["transactions"])
    n_cl  = len(payload["clusters"])
    n_multi = sum(1 for c in payload["clusters"] if len(c["addresses"]) > 1)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>BTxC Forensix — A tool for forensic analysis of IOTA funds</title>
<script src="https://d3js.org/d3.v7.min.js"></script>
<style>
*,*::before,*::after {{ box-sizing:border-box; margin:0; padding:0; }}
:root {{
  --bg:#f5f4ee; --paper:#ffffff; --ink:#1a1a1a; --ink-soft:#4a4a4a;
  --muted:#8a8a82; --rule:#d8d4c7; --rule-soft:#ebe7da;
  --accent:#2563a8; --node:#5a8caf; --node-stk:#2c4f70;
  --yellow:#d9a441; --pink:#c8588f; --green:#4a7e3a; --red:#b13d3d;
}}
html,body {{ height:100%; background:var(--bg); color:var(--ink);
  font-family:'Iowan Old Style','Palatino Linotype',Georgia,serif; overflow:hidden; }}

/* ── header ── */
header {{ border-bottom:2px solid var(--ink); background:var(--paper);
  padding:14px 24px 10px; display:flex; align-items:baseline; justify-content:space-between; }}
header .brand {{ font-size:22px; font-weight:700; letter-spacing:.02em; }}
header .brand small {{ font-size:11px; font-weight:400; color:var(--muted);
  letter-spacing:.06em; text-transform:uppercase; margin-left:12px; }}
header .tagline {{ font-size:13px; color:var(--ink-soft); font-style:italic; }}

/* ── strip ── */
.strip {{ background:var(--paper); border-bottom:1px solid var(--rule);
  padding:6px 24px; display:flex; gap:24px;
  font-size:12px; color:var(--ink-soft); letter-spacing:.04em; }}
.strip span b {{ color:var(--accent); font-weight:700; }}

/* ── tabs ── */
nav.tabs {{ background:var(--paper); border-bottom:2px solid var(--ink);
  padding:0 24px; display:flex; }}
nav.tabs button {{ background:none; border:none; border-bottom:3px solid transparent;
  padding:12px 22px; font-family:inherit; font-size:14px; letter-spacing:.04em;
  color:var(--muted); cursor:pointer; transition:color .15s,border-color .15s; }}
nav.tabs button.active {{ color:var(--ink); border-bottom-color:var(--accent); font-weight:700; }}
nav.tabs button:hover {{ color:var(--ink); }}

/* ── layout ── */
main {{ height:calc(100vh - 116px); }}
.view {{ display:none; height:100%; }}
.view.active {{ display:grid; grid-template-columns:320px 1fr; }}
.view.active.dash-view {{ display:block; overflow-y:auto; }}

/* ── ctrl pane ── */
.ctrl {{ background:var(--paper); border-right:1px solid var(--rule);
  padding:14px 16px 0; overflow-y:auto; display:flex; flex-direction:column; gap:0; }}
.ctrl h2 {{ font-size:10px; text-transform:uppercase; letter-spacing:.14em;
  color:var(--muted); margin:12px 0 6px; font-weight:700; }}
.ctrl h2:first-child {{ margin-top:0; }}
.ctrl button.action {{ display:block; width:100%; padding:8px 12px; margin-bottom:6px;
  font-family:inherit; font-size:13px; font-weight:600; letter-spacing:.02em;
  border:1px solid var(--ink); background:var(--ink); color:#fff;
  cursor:pointer; transition:background .12s; }}
.ctrl button.action.secondary {{ background:var(--paper); color:var(--ink); }}
.ctrl button.action:hover {{ background:var(--accent); border-color:var(--accent); color:#fff; }}
.ctrl button.action.toggled {{ background:var(--accent); border-color:var(--accent); color:#fff; }}
.ctrl button.action.sm {{ padding:5px 10px; font-size:11px; margin-bottom:4px;
  width:auto; display:inline-block; }}
.row {{ display:flex; gap:6px; align-items:center; margin-bottom:6px; }}
.row label {{ font-size:11px; color:var(--muted); width:30px; text-transform:uppercase;
  letter-spacing:.06em; }}
.row input {{ flex:1; font-family:inherit; font-size:13px; padding:5px 8px;
  border:1px solid var(--rule); background:#fafaf6; color:var(--ink); min-width:0; }}
.row input:focus {{ outline:none; border-color:var(--accent); background:#fff; }}
.search-wrap {{ display:flex; gap:4px; margin-bottom:6px; }}
.search-wrap input {{ flex:1; font-family:'Menlo','Consolas',monospace; font-size:11px;
  padding:5px 8px; border:1px solid var(--rule); background:#fafaf6; color:var(--ink); }}
.search-wrap input:focus {{ outline:none; border-color:var(--accent); background:#fff; }}
.search-wrap button {{ padding:5px 10px; font-family:inherit; font-size:11px;
  border:1px solid var(--rule); background:var(--paper); color:var(--ink-soft); cursor:pointer; }}
.search-wrap button:hover {{ border-color:var(--accent); color:var(--accent); }}
.flag-list {{ display:flex; flex-direction:column; gap:3px; margin-bottom:4px; }}
.flag-item {{ display:flex; align-items:center; gap:6px; font-size:12px;
  color:var(--ink-soft); cursor:pointer; }}
.flag-item input[type=checkbox] {{ width:13px; height:13px; cursor:pointer; accent-color:var(--accent); }}
.flag-dot {{ width:10px; height:10px; border-radius:50%; border:1px solid rgba(0,0,0,.2); flex-shrink:0; }}
.flag-row-btns {{ display:flex; gap:4px; margin-bottom:6px; }}
hr.sep {{ border:none; border-top:1px solid var(--rule-soft); margin:10px 0 8px; }}
.leg {{ display:flex; align-items:center; gap:8px; font-size:12px; color:var(--ink-soft); margin-bottom:4px; }}
.leg .dot {{ width:12px; height:12px; border-radius:50%; border:1px solid rgba(0,0,0,.15); }}
.leg .sq  {{ width:12px; height:4px; border-radius:1px; }}
.filter-count {{ font-size:11px; color:var(--muted); margin-bottom:6px; letter-spacing:.02em; }}
.filter-count b {{ color:var(--accent); }}
.output {{ flex:1; margin:10px -16px 0; padding:10px 16px;
  border-top:1px solid var(--rule); background:#fafaf6;
  font-family:'Menlo','Consolas',monospace; font-size:11px; line-height:1.65;
  color:var(--ink); overflow-y:auto; white-space:pre-wrap; min-height:160px; }}
.output .label {{ font-size:10px; color:var(--muted); letter-spacing:.12em;
  text-transform:uppercase; margin-bottom:8px; display:block; }}
.output .yellow {{ color:var(--yellow); font-weight:700; }}
.output .pink   {{ color:var(--pink);   font-weight:700; }}
.output .accent {{ color:var(--accent); font-weight:700; }}
.output .red    {{ color:var(--red);    font-weight:700; }}
.output .green  {{ color:var(--green);  font-weight:700; }}
.output b {{ color:var(--ink); }}

/* ── canvas ── */
.canvas {{ background:
    linear-gradient(0deg,transparent 24px,rgba(0,0,0,.02) 25px),
    linear-gradient(90deg,transparent 24px,rgba(0,0,0,.02) 25px),var(--bg);
  background-size:25px 25px; overflow:hidden; position:relative; }}
svg.stage {{ width:100%; height:100%; cursor:grab; }}
svg.stage:active {{ cursor:grabbing; }}
.tx-node       {{ cursor:pointer; transition:filter .12s; }}
.tx-node:hover {{ filter:brightness(1.2) drop-shadow(0 0 4px rgba(0,0,0,.3)); }}
.cluster-node       {{ cursor:pointer; transition:filter .12s; }}
.cluster-node:hover {{ filter:brightness(1.15) drop-shadow(0 0 4px rgba(0,0,0,.3)); }}
.node-label {{ font-family:'Menlo','Consolas',monospace; font-size:10px; fill:var(--ink);
  pointer-events:none; user-select:none; font-weight:600; }}
.link.dag  {{ stroke:#333; stroke-width:1.4; fill:none; opacity:.55; }}
.link.flow {{ stroke:#2563a8; stroke-width:1.4; fill:none; opacity:.45; }}
.link.highlighted {{ opacity:1 !important; stroke-width:2.2; }}
.link.dimmed      {{ opacity:.06 !important; }}
.fill-normal               {{ fill:#c5d4e2; stroke:#6b8aa6; }}
.fill-sweep                {{ fill:#f5d49b; stroke:#b88835; }}
.fill-wash_trading         {{ fill:#e6a3a3; stroke:#b13d3d; }}
.fill-excess_input_filter  {{ fill:#c3d8b5; stroke:#4a7e3a; }}
.fill-large_value_examiner {{ fill:#b8c8de; stroke:#2c4f70; }}
.fill-first_time_recipient {{ fill:#d9c7e2; stroke:#6b3f8a; }}
.fill-peeling_chain        {{ fill:#fde8c8; stroke:#b85c00; }}
.fill-dust_attack          {{ fill:#f0b8f8; stroke:#8b008b; }}
.fill-dust_linkage         {{ fill:#d8a8e8; stroke:#6a0080; }}
.dimmed {{ opacity:.1 !important; }}
.selected-ring {{ fill:none; stroke:var(--ink); stroke-width:2.5;
  stroke-dasharray:2 3; pointer-events:none; }}
.zoom-btns {{ position:absolute; bottom:14px; right:14px;
  display:flex; flex-direction:column; gap:4px; z-index:10; }}
.zoom-btns button {{ width:30px; height:30px; background:var(--paper);
  border:1px solid var(--rule); font-size:16px; cursor:pointer; color:var(--ink-soft);
  display:flex; align-items:center; justify-content:center; transition:border-color .12s; }}
.zoom-btns button:hover {{ border-color:var(--accent); color:var(--accent); }}

/* ── tooltip ── */
.tooltip {{ position:fixed; display:none; pointer-events:none;
  background:var(--ink); color:#fff; font-family:'Menlo','Consolas',monospace;
  font-size:11px; padding:6px 10px; border-radius:2px;
  max-width:280px; line-height:1.5; z-index:999;
  box-shadow:0 2px 8px rgba(0,0,0,.25); }}
.tooltip .tip-id   {{ font-weight:700; color:#a8c8f0; }}
.tooltip .tip-flag {{ color:#f0c070; }}
.addr {{ font-family:'Menlo',monospace; font-size:10px;
  background:rgba(0,0,0,.04); padding:1px 5px; border-radius:2px; }}

/* ── copy button ── */
.copy-btn {{ background:none; border:none; cursor:pointer; font-size:11px;
  color:var(--muted); padding:1px 4px; border-radius:2px;
  transition:color .1s,background .1s; font-family:inherit; vertical-align:middle; }}
.copy-btn:hover  {{ color:var(--accent); background:rgba(37,99,168,.08); }}
.copy-btn.copied {{ color:var(--green); }}

/* ── Dashboard ── */
.dash-wrap {{ padding:24px 28px; max-width:1400px; margin:0 auto; }}
.dash-section-title {{ font-size:10px; text-transform:uppercase; letter-spacing:.14em;
  color:var(--muted); font-weight:700; margin-bottom:16px; }}
.cards-row {{ display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin-bottom:20px; }}
.card {{ background:var(--paper); border:1px solid var(--rule); padding:16px 18px; }}
.card-label {{ font-size:10px; text-transform:uppercase; letter-spacing:.12em;
  color:var(--muted); margin-bottom:6px; }}
.card-value {{ font-size:28px; font-weight:700; color:var(--accent); line-height:1; margin-bottom:4px; }}
.card-sub   {{ font-size:11px; color:var(--ink-soft); }}
.charts-row {{ display:grid; grid-template-columns:1fr 1fr; gap:14px; margin-bottom:14px; }}
.chart-box {{ background:var(--paper); border:1px solid var(--rule); padding:16px 18px; margin-bottom:14px; }}
.chart-box h3 {{ font-size:10px; text-transform:uppercase; letter-spacing:.12em;
  color:var(--muted); margin-bottom:14px; font-weight:700; }}
.donut-wrap {{ display:flex; gap:20px; align-items:center; }}
.donut-legend {{ flex:1; display:flex; flex-direction:column; gap:6px; }}
.donut-legend-item {{ display:flex; align-items:center; gap:8px;
  font-size:12px; color:var(--ink-soft); }}
.donut-legend-swatch {{ width:12px; height:12px; border-radius:2px; flex-shrink:0; }}
.donut-legend-pct {{ margin-left:auto; font-family:'Menlo',monospace; font-size:11px;
  color:var(--ink); font-weight:600; }}
.donut-legend-count {{ font-family:'Menlo',monospace; font-size:10px; color:var(--muted); }}
.charts-row .chart-box {{ margin-bottom:0; }}
.susp-table {{ width:100%; border-collapse:collapse; font-size:12px; }}
.susp-table th {{ font-size:10px; text-transform:uppercase; letter-spacing:.1em;
  color:var(--muted); font-weight:700; border-bottom:1px solid var(--rule);
  padding:6px 8px; text-align:left; }}
.susp-table td {{ padding:6px 8px; border-bottom:1px solid var(--rule-soft);
  color:var(--ink-soft); vertical-align:middle; }}
.susp-table tr:last-child td {{ border-bottom:none; }}
.susp-table tr:hover td {{ background:#f5f4ee; }}
.tx-id {{ font-family:'Menlo',monospace; font-weight:700; color:var(--accent); }}
.flag-pill {{ display:inline-block; padding:1px 6px; border-radius:2px; font-size:10px;
  font-family:'Menlo',monospace; font-weight:600; margin-right:3px; }}
</style>
</head>
<body>

<header>
  <div class="brand">BTxC Forensix <small>IOTA / BTC Forensic Tool</small></div>
  <div class="tagline">A tool for forensic analysis of IOTA funds</div>
</header>
<div class="strip">
  <span>TRANSACTIONS <b>{n_tx}</b></span>
  <span>CLUSTERS <b>{n_cl}</b></span>
  <span>MULTI-ADDR ENTITIES <b>{n_multi}</b></span>
</div>

<nav class="tabs">
  <button class="tab active" data-view="tx">Transaction View</button>
  <button class="tab"        data-view="cl">Cluster View</button>
  <button class="tab"        data-view="dash">Dashboard</button>
</nav>

<main>

<!-- ════ TRANSACTION VIEW ════ -->
<div id="view-tx" class="view active">
  <aside class="ctrl">
    <h2>Transaction View</h2>
    <button class="action"           onclick="renderTxView()">Show DAG</button>
    <button class="action secondary" onclick="resetAll()">Reset All</button>
    <hr class="sep">
    <h2>Search Address</h2>
    <div class="search-wrap">
      <input type="text" id="addr-search" placeholder="Paste partial address…" oninput="onAddrSearch(this.value)">
      <button onclick="clearSearch()">✕</button>
    </div>
    <hr class="sep">
    <h2>Filter by Flag Type</h2>
    <div class="flag-row-btns">
      <button class="action sm secondary" onclick="setAllFlags(true)">All</button>
      <button class="action sm secondary" onclick="setAllFlags(false)">None</button>
    </div>
    <div class="flag-list" id="flag-checks"></div>
    <hr class="sep">
    <h2>Filter by Transaction ID</h2>
    <div class="row"><label>From</label><input type="number" id="tx-from" min="1" placeholder="e.g. 1"></div>
    <div class="row"><label>To</label>  <input type="number" id="tx-to"   min="1" placeholder="e.g. 50"></div>
    <button class="action secondary" onclick="applyTxFilter()">Apply</button>
    <hr class="sep">
    <h2>Export</h2>
    <button class="action secondary sm" onclick="exportTxCSV()">Download filtered CSV</button>
    <div class="filter-count" id="tx-count"></div>
    <div class="output" id="tx-output"><span class="label">Output Window</span>Click a node to inspect.
Hover for a quick summary. Press <b>Esc</b> to deselect.</div>
  </aside>
  <div class="canvas" id="tx-canvas">
    <svg id="tx-svg" class="stage"></svg>
    <div class="zoom-btns">
      <button onclick="zoomBy('tx',1.35)">+</button>
      <button onclick="zoomFit('tx')" style="font-size:12px">⊡</button>
      <button onclick="zoomBy('tx',0.74)">−</button>
    </div>
  </div>
</div>

<!-- ════ CLUSTER VIEW ════ -->
<div id="view-cl" class="view">
  <aside class="ctrl">
    <h2>Cluster View</h2>
    <button class="action"           id="btn-show-flow" onclick="toggleFlow()">Show fund flow</button>
    <button class="action secondary" onclick="resetClFilter()">Reset Filter</button>
    <hr class="sep">
    <h2>Search Address</h2>
    <div class="search-wrap">
      <input type="text" id="cl-addr-search" placeholder="Paste partial address…" oninput="onClAddrSearch(this.value)">
      <button onclick="clearClSearch()">✕</button>
    </div>
    <hr class="sep">
    <h2>Filter by Cluster ID</h2>
    <div class="row"><label>From</label><input type="number" id="cl-from" min="0" placeholder="e.g. 0"></div>
    <div class="row"><label>To</label>  <input type="number" id="cl-to"   min="0" placeholder="e.g. 50"></div>
    <button class="action secondary" onclick="applyClFilter()">Apply</button>
    <div class="filter-count" id="cl-count"></div>
    <hr class="sep">
    <h2>Legend</h2>
    <div class="leg"><div class="dot" style="background:#5a8caf;border-color:#2c4f70"></div>cluster (size ∝ addresses)</div>
    <div class="leg"><div class="sq" style="background:var(--accent)"></div>fund flow between entities</div>
    <div class="output" id="cl-output"><span class="label">Output Window</span>Click a cluster to list addresses.
Toggle "Show fund flow" to draw inter-cluster edges.
Press <b>Esc</b> to deselect.</div>
  </aside>
  <div class="canvas" id="cl-canvas">
    <svg id="cl-svg" class="stage"></svg>
    <div class="zoom-btns">
      <button onclick="zoomBy('cl',1.35)">+</button>
      <button onclick="zoomFit('cl')" style="font-size:12px">⊡</button>
      <button onclick="zoomBy('cl',0.74)">−</button>
    </div>
  </div>
</div>

<!-- ════ DASHBOARD VIEW ════ -->
<div id="view-dash" class="view dash-view">
  <div class="dash-wrap">
    <div class="cards-row" id="dash-cards"></div>
    <div class="charts-row">
      <div class="chart-box">
        <h3>Flag Distribution</h3>
        <div class="donut-wrap">
          <svg id="flag-donut" viewBox="0 0 180 180" width="180" height="180"></svg>
          <div class="donut-legend" id="donut-legend"></div>
        </div>
      </div>
      <div class="chart-box">
        <h3>Cluster Size Distribution</h3>
        <svg id="cluster-hist" viewBox="0 0 560 220" width="100%" style="display:block"></svg>
      </div>
    </div>
    <div class="chart-box">
      <h3>Transaction Timeline by Flag</h3>
      <svg id="timeline-chart" viewBox="0 0 900 200" width="100%" style="display:block"></svg>
    </div>
    <div class="chart-box">
      <h3>Top Suspicious Transactions</h3>
      <table class="susp-table">
        <thead><tr>
          <th>#ID</th><th>Timestamp</th><th>Flags</th>
          <th>Inputs</th><th>Outputs</th><th>Change Address</th>
        </tr></thead>
        <tbody id="susp-tbody"></tbody>
      </table>
    </div>
  </div>
</div>

</main>
<div class="tooltip" id="tooltip"></div>

<script>
// ── Data ──────────────────────────────────────────────────────────
const DATA = {data_json};

const FLAG_TYPES = ['normal','sweep','wash_trading','peeling_chain',
                    'dust_attack','dust_linkage',
                    'excess_input_filter','large_value_examiner','first_time_recipient'];
const FLAG_COLORS = {{
  normal:'#c5d4e2', sweep:'#f5d49b', wash_trading:'#e6a3a3', peeling_chain:'#fde8c8',
  dust_attack:'#f0b8f8', dust_linkage:'#d8a8e8',
  excess_input_filter:'#c3d8b5', large_value_examiner:'#b8c8de', first_time_recipient:'#d9c7e2',
}};
const FLAG_STROKE = {{
  normal:'#6b8aa6', sweep:'#b88835', wash_trading:'#b13d3d', peeling_chain:'#b85c00',
  dust_attack:'#8b008b', dust_linkage:'#6a0080',
  excess_input_filter:'#4a7e3a', large_value_examiner:'#2c4f70', first_time_recipient:'#6b3f8a',
}};
const FLAG_PILL_COLORS = {{
  normal:               {{bg:'#c5d4e2',color:'#2c4f70'}},
  sweep:                {{bg:'#f5d49b',color:'#7a5800'}},
  wash_trading:         {{bg:'#e6a3a3',color:'#7a1a1a'}},
  peeling_chain:        {{bg:'#fde8c8',color:'#7a3800'}},
  dust_attack:          {{bg:'#f0b8f8',color:'#5a006a'}},
  dust_linkage:         {{bg:'#d8a8e8',color:'#450060'}},
  excess_input_filter:  {{bg:'#c3d8b5',color:'#2a5020'}},
  large_value_examiner: {{bg:'#b8c8de',color:'#1a3050'}},
  first_time_recipient: {{bg:'#d9c7e2',color:'#3d1a5a'}},
}};

const primaryFlag = tx => {{
  const order = ['dust_attack','dust_linkage','wash_trading','sweep','peeling_chain',
                 'excess_input_filter','large_value_examiner','first_time_recipient','normal'];
  for (const f of order) if (tx.flags.includes(f)) return f;
  return 'normal';
}};

function shortAddr(a) {{ return a.slice(0,8)+'…'+a.slice(-6); }}
function fmt(v)        {{ return v.toLocaleString()+' i'; }}

const ADDR2CL = {{}};
for (const c of DATA.clusters) for (const a of c.addresses) ADDR2CL[a] = c.id;

const CL_EDGES = (() => {{
  const map = {{}};
  for (const tx of DATA.transactions) {{
    if (!tx.inputs.length) continue;
    const srcs = new Set(tx.inputs .map(i => ADDR2CL[i.addr]));
    const tgts = new Set(tx.outputs.map(o => ADDR2CL[o.addr]));
    for (const s of srcs) for (const t of tgts) {{
      if (s===t || s==null || t==null) continue;
      const k = s<t ? s+'-'+t : t+'-'+s;
      map[k] = (map[k]||0)+1;
    }}
  }}
  return Object.entries(map).map(([k,v]) => {{
    const [a,b] = k.split('-').map(Number);
    return {{source:a, target:b, count:v}};
  }});
}})();

// ── Tooltip ───────────────────────────────────────────────────────
const tip = document.getElementById('tooltip');
function showTip(e,html) {{
  tip.innerHTML = html; tip.style.display = 'block'; moveTip(e);
}}
function moveTip(e) {{
  const x=e.clientX+14, y=e.clientY-10;
  const tw=tip.offsetWidth, th=tip.offsetHeight;
  tip.style.left = (x+tw>window.innerWidth  ? x-tw-28 : x)+'px';
  tip.style.top  = (y+th>window.innerHeight ? y-th-10 : y)+'px';
}}
function hideTip() {{ tip.style.display='none'; }}

// ── Copy to clipboard ─────────────────────────────────────────────
function copyToClipboard(text, btn) {{
  navigator.clipboard.writeText(text).then(() => {{
    if (!btn) return;
    btn.textContent = '✓'; btn.classList.add('copied');
    setTimeout(() => {{ btn.textContent = '⧉'; btn.classList.remove('copied'); }}, 1200);
  }}).catch(()=>{{}});
}}

// ── Tabs ──────────────────────────────────────────────────────────
let dashRendered = false;
document.querySelectorAll('nav.tabs .tab').forEach(btn => {{
  btn.addEventListener('click', () => {{
    document.querySelectorAll('nav.tabs .tab').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('main .view').forEach(v => v.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('view-'+btn.dataset.view).classList.add('active');
    if (btn.dataset.view === 'dash' && !dashRendered) {{
      renderDashboard(); dashRendered = true;
    }}
  }});
}});

// ── Flag checkboxes ───────────────────────────────────────────────
const flagChecks = {{}};
FLAG_TYPES.forEach(f => {{
  flagChecks[f] = true;
  const label = document.createElement('label');
  label.className = 'flag-item';
  const cb = document.createElement('input');
  cb.type = 'checkbox'; cb.checked = true;
  cb.addEventListener('change', () => {{ flagChecks[f]=cb.checked; renderTxView(); }});
  const dot = document.createElement('div');
  dot.className = 'flag-dot'; dot.style.background = FLAG_COLORS[f];
  const span = document.createElement('span');
  span.textContent = f.replace(/_/g,' ');
  label.append(cb, dot, span);
  document.getElementById('flag-checks').appendChild(label);
}});
function setAllFlags(val) {{
  document.querySelectorAll('#flag-checks input').forEach((cb,i) => {{
    cb.checked = val; flagChecks[FLAG_TYPES[i]] = val;
  }});
  renderTxView();
}}

// ── Zoom helpers ──────────────────────────────────────────────────
const zooms = {{}};
let txNodes=[], clNodes=[];
function zoomBy(id,k) {{
  d3.select('#'+id+'-svg').transition().duration(280).call(zooms[id].scaleBy, k);
}}
function zoomFit(id) {{
  const nodes = id==='tx' ? txNodes : clNodes;
  if (!nodes.length) return;
  const svg = d3.select('#'+id+'-svg');
  const W=svg.node().clientWidth, H=svg.node().clientHeight;
  const xs=nodes.map(n=>n.x||0), ys=nodes.map(n=>n.y||0);
  const x0=Math.min(...xs)-30, x1=Math.max(...xs)+30;
  const y0=Math.min(...ys)-30, y1=Math.max(...ys)+30;
  const scale=Math.min(0.9, 0.9*Math.min(W/(x1-x0||1), H/(y1-y0||1)));
  const tx=W/2-scale*(x0+x1)/2, ty=H/2-scale*(y0+y1)/2;
  svg.transition().duration(500)
     .call(zooms[id].transform, d3.zoomIdentity.translate(tx,ty).scale(scale));
}}

// ── Address search (tx view) ──────────────────────────────────────
let searchQuery='';
function onAddrSearch(q) {{ searchQuery=q.trim().toLowerCase(); applyTxHighlight(); }}
function clearSearch() {{
  document.getElementById('addr-search').value='';
  searchQuery=''; applyTxHighlight();
}}
function applyTxHighlight() {{
  if (!txNodeSel) return;
  if (!searchQuery) {{
    txNodeSel.classed('dimmed',false);
    txLinkSel&&txLinkSel.classed('dimmed',false).classed('highlighted',false);
    return;
  }}
  const matchIds = new Set(DATA.transactions
    .filter(tx => [...tx.inputs,...tx.outputs].some(x=>x.addr.toLowerCase().includes(searchQuery)))
    .map(tx=>tx.id));
  txNodeSel.classed('dimmed', n=>!matchIds.has(n.id));
  txLinkSel&&txLinkSel.classed('dimmed', l=>!matchIds.has(l.source.id)&&!matchIds.has(l.target.id));
  const inp = document.getElementById('addr-search');
  inp.style.borderColor = matchIds.size ? 'var(--green)' : 'var(--red)';
  inp.title = matchIds.size ? matchIds.size+' tx matched' : 'No match';
}}

// ── Address search (cluster view) ─────────────────────────────────
let clSearchQuery='';
function onClAddrSearch(q) {{ clSearchQuery=q.trim().toLowerCase(); applyClAddrHighlight(); }}
function clearClSearch() {{
  document.getElementById('cl-addr-search').value='';
  clSearchQuery=''; applyClAddrHighlight();
}}
function applyClAddrHighlight() {{
  if (!clNodeSel) return;
  if (!clSearchQuery) {{
    clNodeSel.classed('dimmed',false);
    clLinkSel&&clLinkSel.classed('dimmed',false);
    return;
  }}
  const matchIds = new Set(DATA.clusters
    .filter(c=>c.addresses.some(a=>a.toLowerCase().includes(clSearchQuery)))
    .map(c=>c.id));
  clNodeSel.classed('dimmed', n=>!matchIds.has(n.id));
  clLinkSel&&clLinkSel.classed('dimmed', l=>!matchIds.has(l.source.id)&&!matchIds.has(l.target.id));
  const inp = document.getElementById('cl-addr-search');
  inp.style.borderColor = matchIds.size ? 'var(--green)' : 'var(--red)';
}}

// ── Export CSV ────────────────────────────────────────────────────
function exportTxCSV() {{
  const subset = getTxSubset();
  const rows = [['id','timestamp','type','flags','n_inputs','n_outputs','change_address','detected_by']];
  for (const tx of subset)
    rows.push([tx.id, tx.timestamp, tx.type, tx.flags.join('|'),
               tx.inputs.length, tx.outputs.length,
               tx.change_address||'', tx.detected_by||'']);
  const csv = rows.map(r=>r.map(v=>`"${{String(v).replace(/"/g,'""')}}"`).join(',')).join('\\n');
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([csv],{{type:'text/csv'}}));
  a.download = 'btxc_forensix_filtered.csv';
  a.click();
}}

// ── TRANSACTION VIEW ──────────────────────────────────────────────
let txSim=null, txNodeSel=null, txLinkSel=null, activeSim=null;
let txFilter={{from:null,to:null}};
let selectedTxId=null;

function getTxSubset() {{
  return DATA.transactions.filter(tx => {{
    if (txFilter.from!==null && tx.id<txFilter.from) return false;
    if (txFilter.to  !==null && tx.id>txFilter.to)   return false;
    return flagChecks[primaryFlag(tx)] !== false;
  }});
}}
function applyTxFilter() {{
  const f=document.getElementById('tx-from').value.trim();
  const t=document.getElementById('tx-to'  ).value.trim();
  txFilter.from = f!=='' ? parseInt(f) : null;
  txFilter.to   = t!=='' ? parseInt(t) : null;
  renderTxView();
}}
function resetAll() {{
  txFilter={{from:null,to:null}};
  document.getElementById('tx-from').value='';
  document.getElementById('tx-to'  ).value='';
  clearSearch(); setAllFlags(true); selectedTxId=null; renderTxView();
}}

function renderTxView() {{
  if (txSim) {{ txSim.stop(); txSim=null; }}
  const subset=getTxSubset(), ids=new Set(subset.map(t=>t.id));
  document.getElementById('tx-count').innerHTML =
    `Showing <b>${{subset.length}}</b> / ${{DATA.transactions.length}} transactions`;

  const svg=d3.select('#tx-svg'); svg.selectAll('*').remove();
  txNodeSel=null; txLinkSel=null; txNodes=[];
  if (!subset.length) {{
    svg.append('text').attr('x','50%').attr('y','50%').attr('text-anchor','middle')
       .attr('fill','#8a8a82').text('No transactions match the filter.'); return;
  }}
  const W=svg.node().clientWidth||800, H=svg.node().clientHeight||600;
  const z=d3.zoom().scaleExtent([0.15,5]).on('zoom', e=>root.attr('transform',e.transform));
  zooms['tx']=z; svg.call(z);
  const root=svg.append('g');

  svg.append('defs').append('marker').attr('id','arrow-tx')
    .attr('viewBox','0 -4 10 8').attr('refX',16).attr('refY',0)
    .attr('markerWidth',7).attr('markerHeight',7).attr('orient','auto')
    .append('path').attr('d','M0,-4L10,0L0,4').attr('fill','#555');

  const nodes=subset.map(tx=>({{id:tx.id,type:tx.type,flags:tx.flags,tx}}));
  txNodes=nodes;
  const idMap=new Map(nodes.map(n=>[n.id,n]));
  const links=[];
  for (const tx of subset)
    for (const p of tx.parents)
      if (ids.has(p)) links.push({{source:idMap.get(tx.id),target:idMap.get(p)}});

  txLinkSel=root.append('g').selectAll('line').data(links).join('line')
    .attr('class','link dag').attr('marker-end','url(#arrow-tx)');

  txNodeSel=root.append('g').selectAll('circle').data(nodes).join('circle')
    .attr('r',14).attr('class',n=>'tx-node fill-'+primaryFlag(n)).attr('stroke-width',1.5)
    .on('mouseover',(e,d)=>{{
      const tipFlags=d.flags.map(f=>`<span class="tip-flag">${{f}}</span>`).join(' ');
      showTip(e,`<span class="tip-id">#${{d.id}}</span> · ${{d.type}}<br>${{tipFlags}}`);
    }})
    .on('mousemove',moveTip).on('mouseout',hideTip)
    .on('click',(e,d)=>{{e.stopPropagation();onTxClick(d);}})
    .call(d3.drag().on('start',ds).on('drag',dm).on('end',de));

  const labelSel=root.append('g').selectAll('text').data(nodes).join('text')
    .attr('class','node-label').attr('text-anchor','middle').attr('dy',4)
    .text(d=>'#'+d.id).style('pointer-events','none');

  txSim=d3.forceSimulation(nodes)
    .force('link',  d3.forceLink(links).id(d=>d.id).distance(90).strength(0.5))
    .force('charge',d3.forceManyBody().strength(-300))
    .force('center',d3.forceCenter(W/2,H/2))
    .force('collide',d3.forceCollide(22))
    .on('tick',()=>{{
      txLinkSel.attr('x1',d=>d.source.x).attr('y1',d=>d.source.y)
               .attr('x2',d=>d.target.x).attr('y2',d=>d.target.y);
      txNodeSel.attr('cx',d=>d.x).attr('cy',d=>d.y);
      labelSel.attr('x',d=>d.x).attr('y',d=>d.y);
    }})
    .on('end',()=>{{ if (searchQuery) applyTxHighlight(); }});

  activeSim=txSim;
  svg.on('click',()=>clearSelection('tx'));
}}

function onTxClick(node) {{
  selectedTxId=node.id;
  const nbIds=new Set([node.id]);
  txLinkSel.each(l=>{{
    if (l.source.id===node.id) nbIds.add(l.target.id);
    if (l.target.id===node.id) nbIds.add(l.source.id);
  }});
  txNodeSel.classed('dimmed',n=>!nbIds.has(n.id)).classed('selected',n=>n.id===node.id);
  txLinkSel.classed('dimmed',l=>l.source.id!==node.id&&l.target.id!==node.id)
           .classed('highlighted',l=>l.source.id===node.id||l.target.id===node.id);
  d3.select('#tx-svg').selectAll('.selected-ring').remove();
  d3.select('#tx-svg g').append('circle').attr('class','selected-ring')
    .attr('r',19).attr('cx',node.x).attr('cy',node.y);

  const tx=node.tx;
  const mkCopy = addr =>
    `<button class="copy-btn" onclick="copyToClipboard('${{addr}}',this)" title="Copy">⧉</button>`;
  const inLines=tx.inputs.map(i=>
    `  <span class="yellow">●</span> <span class="addr">${{shortAddr(i.addr)}}</span>  ${{fmt(i.val)}} ${{mkCopy(i.addr)}}`).join('\\n');
  const outLines=tx.outputs.map(o=>
    `  <span class="pink">●</span> <span class="addr">${{shortAddr(o.addr)}}</span>  ${{fmt(o.val)}} ${{mkCopy(o.addr)}}`).join('\\n');
  const flagPills=tx.flags.map(f=>{{
    const cls=f==='wash_trading'||f==='dust_attack'||f==='dust_linkage'?'red':f==='normal'?'green':'accent';
    return `<span class="${{cls}}">[${{f}}]</span>`;
  }}).join(' ');
  const change=tx.change_address
    ? `\\n<b>Change (via ${{tx.detected_by}}):</b>\\n  <span class="addr">${{shortAddr(tx.change_address)}}</span> ${{mkCopy(tx.change_address)}}`
    : '';
  const nbs=[...nbIds].filter(id=>id!==node.id);
  const nbStr=nbs.length ? `\\n<b>Neighbours:</b> ${{nbs.map(id=>'#'+id).join(', ')}}` : '';
  document.getElementById('tx-output').innerHTML =
    `<span class="label">Transaction #${{tx.id}}</span>` +
    `<b>Timestamp:</b> ${{tx.timestamp}}\\n<b>Type:</b> ${{tx.type}}\\n<b>Flags:</b> ${{flagPills}}\\n` +
    `<b>Parents:</b> ${{tx.parents.length ? tx.parents.map(p=>'#'+p).join(', ') : '— genesis'}}` +
    change + nbStr +
    `\\n\\n<b>Inputs (yellow):</b>\\n${{inLines}}\\n\\n<b>Outputs (pink):</b>\\n${{outLines}}`;
}}

function clearSelection(id) {{
  if (id==='tx') {{
    txNodeSel&&txNodeSel.classed('dimmed',false);
    txLinkSel&&txLinkSel.classed('dimmed',false).classed('highlighted',false);
    d3.select('#tx-svg').selectAll('.selected-ring').remove();
    selectedTxId=null;
  }} else {{
    clNodeSel&&clNodeSel.classed('dimmed',false);
    clLinkSel&&clLinkSel.classed('dimmed',false).classed('highlighted',false);
    d3.select('#cl-svg').selectAll('.selected-ring').remove();
    selectedClId=null;
  }}
}}

// ── CLUSTER VIEW ──────────────────────────────────────────────────
let clSim=null, clNodeSel=null, clLinkSel=null;
let showFlow=false, clFilter={{from:null,to:null}}, selectedClId=null;

function getClSubset() {{
  let cls=DATA.clusters.filter(c=>c.addresses.length>1);
  if (clFilter.from!==null) cls=cls.filter(c=>c.id>=clFilter.from);
  if (clFilter.to  !==null) cls=cls.filter(c=>c.id<=clFilter.to);
  return cls;
}}
function applyClFilter() {{
  const f=document.getElementById('cl-from').value.trim();
  const t=document.getElementById('cl-to'  ).value.trim();
  clFilter.from=f!==''?parseInt(f):null; clFilter.to=t!==''?parseInt(t):null;
  renderClView();
}}
function resetClFilter() {{
  clFilter={{from:null,to:null}};
  document.getElementById('cl-from').value='';
  document.getElementById('cl-to'  ).value='';
  renderClView();
}}
function toggleFlow() {{
  showFlow=!showFlow;
  document.getElementById('btn-show-flow').classList.toggle('toggled',showFlow);
  renderClView();
}}

function renderClView() {{
  if (clSim) {{ clSim.stop(); clSim=null; }}
  const subset=getClSubset(), idSet=new Set(subset.map(c=>c.id));
  document.getElementById('cl-count').innerHTML=
    `Showing <b>${{subset.length}}</b> multi-address clusters`;

  const svg=d3.select('#cl-svg'); svg.selectAll('*').remove();
  clNodeSel=null; clLinkSel=null; clNodes=[];
  if (!subset.length) {{
    svg.append('text').attr('x','50%').attr('y','50%').attr('text-anchor','middle')
       .attr('fill','#8a8a82').text('No clusters match the filter.'); return;
  }}
  const W=svg.node().clientWidth||800, H=svg.node().clientHeight||600;
  const z=d3.zoom().scaleExtent([0.1,5]).on('zoom',e=>root.attr('transform',e.transform));
  zooms['cl']=z; svg.call(z);
  const root=svg.append('g');

  const nodes=subset.map(c=>({{id:c.id,size:c.addresses.length,addresses:c.addresses}}));
  clNodes=nodes;
  const idMap=new Map(nodes.map(n=>[n.id,n]));
  const edges=showFlow
    ? CL_EDGES.filter(e=>idSet.has(e.source)&&idSet.has(e.target))
              .map(e=>({{source:idMap.get(e.source),target:idMap.get(e.target),count:e.count}}))
    : [];

  const maxSize=d3.max(nodes,d=>d.size)||1;
  const rScale=d3.scaleSqrt().domain([1,maxSize]).range([12,42]);

  clLinkSel=root.append('g').selectAll('line').data(edges).join('line')
    .attr('class','link flow')
    .attr('stroke-width',d=>Math.max(1,Math.log(d.count+1)*1.4));

  clNodeSel=root.append('g').selectAll('circle').data(nodes).join('circle')
    .attr('r',d=>rScale(d.size)).attr('class','cluster-node')
    .attr('fill','#5a8caf').attr('stroke','#2c4f70').attr('stroke-width',1.5).attr('opacity',.92)
    .on('mouseover',(e,d)=>showTip(e,`<span class="tip-id">Cluster #${{d.id}}</span><br>${{d.size}} address${{d.size>1?'es':''}}`))
    .on('mousemove',moveTip).on('mouseout',hideTip)
    .on('click',(e,d)=>{{e.stopPropagation();onClClick(d);}})
    .call(d3.drag().on('start',ds).on('drag',dm).on('end',de));

  const labelSel=root.append('g').selectAll('text').data(nodes).join('text')
    .attr('class','node-label').attr('text-anchor','middle').attr('dy',3)
    .attr('fill','#fff').text(d=>'#'+d.id).style('pointer-events','none');

  clSim=d3.forceSimulation(nodes)
    .force('link',  d3.forceLink(edges).id(d=>d.id).distance(150).strength(0.35))
    .force('charge',d3.forceManyBody().strength(-500))
    .force('center',d3.forceCenter(W/2,H/2))
    .force('collide',d3.forceCollide(d=>rScale(d.size)+12))
    .on('tick',()=>{{
      clLinkSel.attr('x1',d=>d.source.x).attr('y1',d=>d.source.y)
               .attr('x2',d=>d.target.x).attr('y2',d=>d.target.y);
      clNodeSel.attr('cx',d=>d.x).attr('cy',d=>d.y);
      labelSel.attr('x',d=>d.x).attr('y',d=>d.y);
    }});

  activeSim=clSim;
  svg.on('click',()=>clearSelection('cl'));
}}

function onClClick(d) {{
  selectedClId=d.id;
  const nbIds=new Set([d.id]);
  clLinkSel&&clLinkSel.each(l=>{{
    if (l.source.id===d.id) nbIds.add(l.target.id);
    if (l.target.id===d.id) nbIds.add(l.source.id);
  }});
  clNodeSel.classed('dimmed',n=>!nbIds.has(n.id));
  clLinkSel&&clLinkSel
    .classed('dimmed',l=>l.source.id!==d.id&&l.target.id!==d.id)
    .classed('highlighted',l=>l.source.id===d.id||l.target.id===d.id);

  const maxSize=d3.max(DATA.clusters,c=>c.addresses.length)||1;
  const r=Math.sqrt(d.size/maxSize)*42+12;
  d3.select('#cl-svg').selectAll('.selected-ring').remove();
  d3.select('#cl-svg g').append('circle').attr('class','selected-ring')
    .attr('r',r+6).attr('cx',d.x).attr('cy',d.y);

  const mkCopy = addr =>
    `<button class="copy-btn" onclick="copyToClipboard('${{addr}}',this)" title="Copy">⧉</button>`;
  const list=d.addresses.slice(0,25)
    .map(a=>`  <span class="addr">${{shortAddr(a)}}</span> ${{mkCopy(a)}}`).join('\\n');
  const more=d.addresses.length>25?`\\n  … and ${{d.addresses.length-25}} more`:'';
  document.getElementById('cl-output').innerHTML =
    `<span class="label">Cluster #${{d.id}}</span>` +
    `<b>Size:</b> ${{d.addresses.length}} address${{d.addresses.length!==1?'es':''}}\\n\\n` +
    `<b>Member addresses:</b>\\n${{list}}${{more}}`;
}}

// ── DASHBOARD ─────────────────────────────────────────────────────
function renderDashboard() {{
  const flagCounts = {{}};
  FLAG_TYPES.forEach(f=>flagCounts[f]=0);
  for (const tx of DATA.transactions) flagCounts[primaryFlag(tx)]++;

  const nSuspicious = DATA.transactions.length - flagCounts['normal'];
  const suspPct = (nSuspicious/DATA.transactions.length*100).toFixed(1);
  const nAddr = DATA.clusters.reduce((s,c)=>s+c.addresses.length,0);
  const nMulti = DATA.clusters.filter(c=>c.addresses.length>1).length;

  document.getElementById('dash-cards').innerHTML = [
    {{label:'Total Transactions',value:DATA.transactions.length.toLocaleString(),sub:'loaded from CSV'}},
    {{label:'Suspicious',value:nSuspicious.toLocaleString(),sub:suspPct+'% of transactions'}},
    {{label:'Unique Addresses',value:nAddr.toLocaleString(),sub:'across all clusters'}},
    {{label:'Multi-Addr Clusters',value:nMulti.toLocaleString(),sub:'of '+DATA.clusters.length.toLocaleString()+' total'}},
  ].map(c=>`<div class="card">
    <div class="card-label">${{c.label}}</div>
    <div class="card-value">${{c.value}}</div>
    <div class="card-sub">${{c.sub}}</div>
  </div>`).join('');

  buildFlagDonut(flagCounts);
  buildClusterHistogram();
  buildTimeline();
  buildSuspTable();
}}

function buildFlagDonut(flagCounts) {{
  const svg=d3.select('#flag-donut');
  svg.selectAll('*').remove();
  const W=180,H=180,R=70,iR=42;
  const data=FLAG_TYPES.map(f=>({{f,count:flagCounts[f]}})).filter(d=>d.count>0);
  const total=d3.sum(data,d=>d.count);
  const pie=d3.pie().value(d=>d.count).sort(null);
  const arc=d3.arc().innerRadius(iR).outerRadius(R);
  const g=svg.append('g').attr('transform',`translate(${{W/2}},${{H/2}})`);

  g.selectAll('path').data(pie(data)).join('path')
    .attr('d',arc)
    .attr('fill',d=>FLAG_COLORS[d.data.f])
    .attr('stroke',d=>FLAG_STROKE[d.data.f])
    .attr('stroke-width',1)
    .on('mouseover',function(e,d){{
      d3.select(this).attr('opacity',.8);
      showTip(e,`<span class="tip-flag">${{d.data.f.replace(/_/g,' ')}}</span><br>${{d.data.count}} (${{(d.data.count/total*100).toFixed(1)}}%)`);
    }})
    .on('mousemove',moveTip)
    .on('mouseout',function(){{ d3.select(this).attr('opacity',1); hideTip(); }});

  g.append('text').attr('text-anchor','middle').attr('dy','-.2em')
    .attr('font-size','18px').attr('font-weight','700').attr('fill','var(--ink)').text(total.toLocaleString());
  g.append('text').attr('text-anchor','middle').attr('dy','1.1em')
    .attr('font-size','9px').attr('fill','var(--muted)').attr('letter-spacing','.08em').text('TRANSACTIONS');

  document.getElementById('donut-legend').innerHTML = data.map(d=>
    `<div class="donut-legend-item">
      <div class="donut-legend-swatch" style="background:${{FLAG_COLORS[d.f]}};border:1px solid ${{FLAG_STROKE[d.f]}}"></div>
      <span>${{d.f.replace(/_/g,' ')}}</span>
      <span class="donut-legend-count">${{d.count}}</span>
      <span class="donut-legend-pct">${{(d.count/total*100).toFixed(1)}}%</span>
    </div>`
  ).join('');
}}

function buildClusterHistogram() {{
  const margin={{top:10,right:10,bottom:40,left:44}};
  const vW=560, vH=220;
  const iW=vW-margin.left-margin.right, iH=vH-margin.top-margin.bottom;
  const svg=d3.select('#cluster-hist').attr('viewBox',`0 0 ${{vW}} ${{vH}}`);
  svg.selectAll('*').remove();

  const binData={{}};
  for (const c of DATA.clusters) {{
    const k=Math.min(c.addresses.length,20);
    binData[k]=(binData[k]||0)+1;
  }}
  const bars=Object.entries(binData).map(([k,v])=>({{size:+k,count:v}})).sort((a,b)=>a.size-b.size);

  const x=d3.scaleBand().domain(bars.map(d=>d.size)).range([0,iW]).padding(.2);
  const y=d3.scaleLinear().domain([0,d3.max(bars,d=>d.count)]).nice().range([iH,0]);
  const g=svg.append('g').attr('transform',`translate(${{margin.left}},${{margin.top}})`);

  g.append('g').attr('transform',`translate(0,${{iH}})`)
   .call(d3.axisBottom(x).tickFormat(d=>d>=20?'20+':d))
   .selectAll('text').attr('font-size','9px').attr('fill','var(--muted)');
  g.append('g').call(d3.axisLeft(y).ticks(5).tickSize(-iW))
   .selectAll('text').attr('font-size','9px').attr('fill','var(--muted)');
  g.selectAll('.domain').attr('stroke','var(--rule)');
  g.selectAll('.tick line').attr('stroke','var(--rule-soft)').attr('stroke-dasharray','2,2');

  g.selectAll('rect').data(bars).join('rect')
    .attr('x',d=>x(d.size)).attr('y',d=>y(d.count))
    .attr('width',x.bandwidth()).attr('height',d=>iH-y(d.count))
    .attr('fill','#5a8caf').attr('opacity',.85)
    .on('mouseover',function(e,d){{
      d3.select(this).attr('opacity',1);
      showTip(e,`Size ${{d.size>=20?'20+':d.size}}<br><b>${{d.count}}</b> cluster${{d.count!==1?'s':''}}`);
    }})
    .on('mousemove',moveTip)
    .on('mouseout',function(){{ d3.select(this).attr('opacity',.85); hideTip(); }});

  svg.append('text').attr('x',vW/2).attr('y',vH-2)
    .attr('text-anchor','middle').attr('font-size','9px').attr('fill','var(--muted)')
    .attr('letter-spacing','.08em').text('CLUSTER SIZE (addresses)');
}}

function buildTimeline() {{
  const N=20;
  const margin={{top:10,right:10,bottom:46,left:44}};
  const vW=900, vH=200;
  const iW=vW-margin.left-margin.right, iH=vH-margin.top-margin.bottom;
  const svg=d3.select('#timeline-chart').attr('viewBox',`0 0 ${{vW}} ${{vH}}`);
  svg.selectAll('*').remove();

  const txs=DATA.transactions.map(tx=>({{t:new Date(tx.timestamp),flag:primaryFlag(tx)}}))
    .filter(d=>!isNaN(d.t));
  if (!txs.length) return;

  const tMin=d3.min(txs,d=>d.t), tMax=d3.max(txs,d=>d.t);
  const span=Math.max(tMax-tMin,1);
  const bw=span/N;

  const bins=Array.from({{length:N}},(_,i)=>{{
    const o={{i}}; FLAG_TYPES.forEach(f=>o[f]=0); return o;
  }});
  for (const tx of txs) {{
    const bi=Math.min(N-1,Math.floor((tx.t-tMin)/bw));
    bins[bi][tx.flag]++;
  }}

  const x=d3.scaleBand().domain(d3.range(N)).range([0,iW]).padding(.1);
  const maxTotal=d3.max(bins,d=>FLAG_TYPES.reduce((s,f)=>s+d[f],0));
  const y=d3.scaleLinear().domain([0,maxTotal]).nice().range([iH,0]);
  const stack=d3.stack().keys(FLAG_TYPES)(bins);

  const g=svg.append('g').attr('transform',`translate(${{margin.left}},${{margin.top}})`);
  g.append('g').call(d3.axisLeft(y).ticks(4).tickSize(-iW))
   .selectAll('text').attr('font-size','9px').attr('fill','var(--muted)');
  g.selectAll('.domain').attr('stroke','var(--rule)');
  g.selectAll('.tick line').attr('stroke','var(--rule-soft)').attr('stroke-dasharray','2,2');

  stack.forEach(layer=>{{
    g.selectAll(`.tl-${{layer.key}}`).data(layer).join('rect')
      .attr('class',`tl-${{layer.key}}`)
      .attr('x',d=>x(d.data.i)).attr('y',d=>y(d[1]))
      .attr('height',d=>Math.max(0,y(d[0])-y(d[1]))).attr('width',x.bandwidth())
      .attr('fill',FLAG_COLORS[layer.key]).attr('stroke',FLAG_STROKE[layer.key]).attr('stroke-width',.4)
      .on('mouseover',function(e,d){{
        const ts=new Date(tMin.getTime()+d.data.i*bw);
        const total=FLAG_TYPES.reduce((s,f)=>s+d.data[f],0);
        showTip(e,`${{ts.toLocaleDateString()}}<br><b>${{total}}</b> transactions`);
      }})
      .on('mousemove',moveTip).on('mouseout',hideTip);
  }});

  // X date ticks
  const tickIdx=[0,Math.floor(N/4),Math.floor(N/2),Math.floor(3*N/4),N-1];
  const xAxis=g.append('g').attr('transform',`translate(0,${{iH}})`);
  tickIdx.forEach(i=>{{
    const d=new Date(tMin.getTime()+i*bw);
    xAxis.append('text')
      .attr('x',x(i)+x.bandwidth()/2).attr('y',14)
      .attr('text-anchor','middle').attr('font-size','9px').attr('fill','var(--muted)')
      .text(d.toLocaleDateString('en-GB',{{month:'short',day:'numeric',year:'2-digit'}}));
  }});

  // Legend
  let lx=margin.left;
  FLAG_TYPES.forEach(f=>{{
    const label=f.replace(/_/g,' ');
    const lg=svg.append('g').attr('transform',`translate(${{lx}},${{vH-6}})`);
    lg.append('rect').attr('width',9).attr('height',9).attr('y',-9)
      .attr('fill',FLAG_COLORS[f]).attr('stroke',FLAG_STROKE[f]).attr('stroke-width',.5);
    lg.append('text').attr('x',12).attr('font-size','8.5px').attr('fill','var(--muted)').text(label);
    lx += label.length*5.2+20;
  }});
}}

function buildSuspTable() {{
  const PRIO=['dust_attack','dust_linkage','wash_trading','sweep','peeling_chain','excess_input_filter','large_value_examiner','first_time_recipient'];
  const rows=DATA.transactions
    .filter(tx=>tx.flags.some(f=>f!=='normal'))
    .sort((a,b)=>PRIO.indexOf(primaryFlag(a))-PRIO.indexOf(primaryFlag(b)))
    .slice(0,30);

  document.getElementById('susp-tbody').innerHTML=rows.map(tx=>{{
    const pills=tx.flags.map(f=>{{
      const c=FLAG_PILL_COLORS[f]||{{bg:'#eee',color:'#333'}};
      return `<span class="flag-pill" style="background:${{c.bg}};color:${{c.color}}">${{f.replace(/_/g,' ')}}</span>`;
    }}).join('');
    const change=tx.change_address
      ? `<span class="addr">${{shortAddr(tx.change_address)}}</span>
         <button class="copy-btn" onclick="copyToClipboard('${{tx.change_address}}',this)" title="Copy">⧉</button>`
      : '<span style="color:var(--muted)">—</span>';
    return `<tr>
      <td><span class="tx-id">#${{tx.id}}</span></td>
      <td style="font-family:monospace;font-size:10px;white-space:nowrap">${{tx.timestamp}}</td>
      <td>${{pills}}</td>
      <td style="font-family:monospace;font-size:10px;text-align:right">${{tx.inputs.length}}</td>
      <td style="font-family:monospace;font-size:10px;text-align:right">${{tx.outputs.length}}</td>
      <td>${{change}}</td>
    </tr>`;
  }}).join('');
}}

// ── Drag handlers ─────────────────────────────────────────────────
function ds(e,d) {{
  if (!e.active && activeSim) activeSim.alphaTarget(.3).restart();
  d.fx=d.x; d.fy=d.y;
}}
function dm(e,d) {{ d.fx=e.x; d.fy=e.y; }}
function de(e,d) {{
  if (!e.active && activeSim) activeSim.alphaTarget(0);
  d.fx=null; d.fy=null;
}}

// ── Keyboard ──────────────────────────────────────────────────────
document.addEventListener('keydown', e=>{{
  if (e.key==='Escape') {{
    clearSelection('tx'); clearSelection('cl');
    clearSearch(); clearClSearch();
  }}
}});

// ── Init ──────────────────────────────────────────────────────────
window.addEventListener('DOMContentLoaded', renderTxView);
window.addEventListener('resize', ()=>{{ renderTxView(); renderClView(); }});
</script>
</body>
</html>"""


def main() -> None:
    p = argparse.ArgumentParser(description="Render BTxC Forensix GUI.")
    p.add_argument("--input",  default="output/results.json")
    p.add_argument("--output", default="output/btxc_forensix.html")
    args = p.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        payload = json.load(f)

    html = build_html(payload)
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[render]   {args.output}  ({len(html)//1024} KB)")


if __name__ == "__main__":
    main()
