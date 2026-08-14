from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "data" / "routes" / "zangarmarsh-route-atlas-prototype.html"

subprocess.run([sys.executable, str(ROOT / "scripts" / "build_route_atlas_prototype.py")], cwd=ROOT, check=True)
text = HTML.read_text(encoding="utf-8")

text = text.replace(
    '<label>路线层<select id="routeCircle"></select></label>',
    '<div class="route-circle-nav"><span class="route-circle-title">路线</span><div id="routeCircleButtons" class="route-circle-buttons"></div><button id="nextCircle" class="next-circle-btn" type="button">下一圈 →</button></div>',
    1,
)
text = text.replace(
    "circle: document.getElementById('routeCircle'),",
    "circleButtons: document.getElementById('routeCircleButtons'),\n  nextCircle: document.getElementById('nextCircle'),",
    1,
)
text = text.replace(
    "</style>",
    ".route-circle-nav{display:flex;align-items:center;gap:7px;flex-wrap:wrap}.route-circle-title{color:#aeb9c5;font-size:12px}.route-circle-buttons{display:flex;gap:4px}.circle-btn,.next-circle-btn{border:1px solid #3a4654;background:#171d25;color:#dbe4ee;border-radius:7px;padding:5px 9px;cursor:pointer;font-weight:700}.circle-btn:hover,.next-circle-btn:hover{border-color:#ffd36a}.circle-btn.active{background:#ffd36a;color:#151515;border-color:#ffd36a}.next-circle-btn:disabled{opacity:.4;cursor:default}</style>",
    1,
)

init = """const ROUTE_CIRCLES = DATA.route_circles?.circles || [];
let selectedCircleId = ROUTE_CIRCLES.length ? Number(ROUTE_CIRCLES[0].id) : 0;
function renderCircleButtons() {
  controls.circleButtons.innerHTML = ROUTE_CIRCLES.map(c => `<button type=\"button\" class=\"circle-btn${Number(c.id) === selectedCircleId ? ' active' : ''}\" data-circle=\"${c.id}\">${c.id}</button>`).join('');
  controls.circleButtons.querySelectorAll('[data-circle]').forEach(btn => btn.addEventListener('click', () => {
    selectedCircleId = Number(btn.dataset.circle);
    selectedRouteNodeId = null;
    renderCircleButtons();
    renderMarkers();
  }));
  const lastId = ROUTE_CIRCLES.length ? Number(ROUTE_CIRCLES[ROUTE_CIRCLES.length - 1].id) : 0;
  controls.nextCircle.disabled = !ROUTE_CIRCLES.length || selectedCircleId === lastId;
}
renderCircleButtons();
"""
text = text.replace("let selectedNpcId = null;", init + "let selectedNpcId = null;", 1)

new_renderer = r'''function renderRouteLayer() {
  const circleId = Number(controls.circle.value || 0);
  const circle = ROUTE_CIRCLES.find(c => Number(c.id) === circleId);
  const nodes = circle?.nodes || [];
  if (!nodes.length) return;
  const ns = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(ns, 'svg');
  svg.setAttribute('class', 'route-svg');
  svg.setAttribute('viewBox', '0 0 100 100');
  svg.setAttribute('preserveAspectRatio', 'none');
  const defs = document.createElementNS(ns, 'defs');
  const marker = document.createElementNS(ns, 'marker');
  marker.setAttribute('id', 'routeArrow');
  marker.setAttribute('markerWidth', '6');
  marker.setAttribute('markerHeight', '6');
  marker.setAttribute('refX', '5');
  marker.setAttribute('refY', '3');
  marker.setAttribute('orient', 'auto');
  marker.setAttribute('markerUnits', 'strokeWidth');
  const arrow = document.createElementNS(ns, 'path');
  arrow.setAttribute('d', 'M0,0 L6,3 L0,6 z');
  arrow.setAttribute('fill', '#ffd36a');
  marker.appendChild(arrow);
  defs.appendChild(marker);
  svg.appendChild(defs);
  for (let i=0; i<nodes.length-1; i++) {
    const a = nodes[i].point, b = nodes[i+1].point;
    const line = document.createElementNS(ns, 'line');
    line.setAttribute('class', 'route-line');
    line.setAttribute('x1', a[0]); line.setAttribute('y1', a[1]);
    line.setAttribute('x2', b[0]); line.setAttribute('y2', b[1]);
    line.setAttribute('marker-end', 'url(#routeArrow)');
    svg.appendChild(line);
  }
  overlay.appendChild(svg);
  const seen = new Set();
  const sameStartEnd = nodes.length > 1 && nodes[0].point[0] === nodes[nodes.length-1].point[0] && nodes[0].point[1] === nodes[nodes.length-1].point[1];
  nodes.forEach((node, index) => {
    const key = `${node.point[0].toFixed(3)},${node.point[1].toFixed(3)}`;
    if (seen.has(key)) return;
    seen.add(key);
    const button = document.createElement('button');
    button.className = 'route-node' + (node.id === selectedRouteNodeId ? ' selected' : '');
    button.style.left = node.point[0] + '%';
    button.style.top = node.point[1] + '%';
    const seq = index + 1;
    button.textContent = index === 0 && sameStartEnd ? `1/${nodes.length}` : String(seq);
    button.title = `${circle.title} · ${seq}. ${node.title} · ${node.short_action}`;
    button.addEventListener('click', () => showRouteNode(node.id));
    overlay.appendChild(button);
    const label = document.createElement('span');
    label.className = 'route-label';
    label.style.left = node.point[0] + '%';
    label.style.top = node.point[1] + '%';
    label.textContent = index === 0 && sameStartEnd ? `起/终 · ${node.short_action}` : `${seq} ${node.short_action}`;
    overlay.appendChild(label);
  });
}
function routeActionGroup'''
text, count = re.subn(r"function renderRouteLayer\(\) \{.*?\n\}\nfunction routeActionGroup", new_renderer, text, count=1, flags=re.S)
if count != 1:
    raise RuntimeError("renderRouteLayer replacement failed")

text = text.replace("controls.route.addEventListener('change', renderMarkers);", "controls.circle.addEventListener('change', () => { selectedRouteNodeId = null; renderMarkers(); });", 1)

needle = "const actionHtml = routeActionGroup('接任务', node.actions?.accept) + routeActionGroup('做任务', node.actions?.do) + routeActionGroup('交任务', node.actions?.turnin);"
extra = needle + "\n  const otherHtml = (node.other_quests || []).map(row => { const q = quest(row.quest_id); return `<div class=\"relation\"><b>${esc(q?.name || ('任务 ' + row.quest_id))}：</b>${esc(row.status)} · ${esc(row.reason)}</div>`; }).join('');"
text = text.replace(needle, extra, 1)
text = text.replace("${actionHtml || `<div class=\"section\"><h2>本段任务</h2><div class=\"quest-list\">${node.quest_ids.map(qid => questButton(qid)).join('')}</div></div>`}", "${actionHtml || `<div class=\"section\"><h2>本段任务</h2><div class=\"quest-list\">${node.quest_ids.map(qid => questButton(qid)).join('')}</div></div>`}${otherHtml ? `<div class=\"section\"><h2>此区域其他任务</h2>${otherHtml}</div>` : ''}", 1)

HTML.write_text(text, encoding="utf-8")
print(HTML)
