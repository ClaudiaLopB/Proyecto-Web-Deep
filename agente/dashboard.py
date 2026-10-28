"""Genera un dashboard HTML interactivo (un único archivo) a partir del dato limpio y una especificación.

La especificación es un diccionario que puede escribir el agente de IA o el modo automático:

{
  "titulo": str, "subtitulo": str,
  "filtros": [columna, ...],
  "kpis": [{"etiqueta": str, "tipo": "conteo" | "media" | "tasa", "columna": str, "valor": str}],
  "graficos": [{"tipo": "barras" | "tasa" | "histograma" | "linea_tiempo" | "calor" | "mapa",
                "titulo": str, "x": str, "y": str, "color": str,
                "columna": str, "valor": str, "tramos": [números], "explicacion": str,
                "lat": str, "lon": str, "etiqueta": str  (solo mapa)}],
  "hallazgos": [str],
  "pie": str  (opcional, texto del pie de página)
}
"""

from __future__ import annotations

import html
import json
from pathlib import Path

import pandas as pd

from .datos import Session

CHART_TYPES = {"barras", "tasa", "histograma", "linea_tiempo", "calor", "mapa"}


def validate_spec(session: Session, spec: dict) -> list[str]:
    """Devuelve una lista de errores (vacía si la especificación es correcta)."""
    cols = set(session.data.columns)
    errors = []
    for col in spec.get("filtros", []):
        if col not in cols:
            errors.append(f"filtro: columna inexistente '{col}'")
    for kpi in spec.get("kpis", []):
        if kpi.get("tipo") in ("media", "tasa") and kpi.get("columna") not in cols:
            errors.append(f"kpi '{kpi.get('etiqueta')}': columna inexistente '{kpi.get('columna')}'")
    for chart in spec.get("graficos", []):
        if chart.get("tipo") not in CHART_TYPES:
            errors.append(f"gráfico '{chart.get('titulo')}': tipo desconocido '{chart.get('tipo')}'")
        if chart.get("tipo") == "mapa":
            for key, limit in (("lat", 90), ("lon", 180)):
                col = chart.get(key)
                if col not in cols:
                    errors.append(f"gráfico '{chart.get('titulo')}': un mapa necesita '{key}' con una columna existente")
                elif not pd.api.types.is_numeric_dtype(session.data[col]) or session.data[col].abs().max() > limit:
                    errors.append(f"gráfico '{chart.get('titulo')}': '{col}' no son grados de {key}")
        for key in ("x", "y", "color", "columna", "etiqueta"):
            if chart.get(key) and chart[key] not in cols:
                errors.append(f"gráfico '{chart.get('titulo')}': columna inexistente '{chart[key]}' en '{key}'")
        if chart.get("tipo") == "tasa" and not (chart.get("columna") and chart.get("valor") is not None):
            errors.append(f"gráfico '{chart.get('titulo')}': una tasa necesita 'columna' y 'valor'")
    if not spec.get("graficos"):
        errors.append("el dashboard necesita al menos un gráfico")
    return errors


def _column_payload(series: pd.Series) -> dict:
    """Codifica una columna de forma compacta: categorías como índices, números tal cual."""
    if pd.api.types.is_datetime64_any_dtype(series):
        return {"t": "fecha", "v": [None if pd.isna(v) else v.strftime("%Y-%m-%d") for v in series]}
    if pd.api.types.is_numeric_dtype(series):
        return {"t": "num", "v": [None if pd.isna(v) else (int(v) if float(v).is_integer() else round(float(v), 6)) for v in series]}
    cats = sorted(series.dropna().unique().tolist(), key=_natural_key)
    index = {c: i for i, c in enumerate(cats)}
    return {"t": "cat", "c": cats, "v": [None if v is None or pd.isna(v) else index[v] for v in series]}


def _natural_key(text: str):
    """Ordena 'distrito 2' antes que 'distrito 10'."""
    import re

    return [int(p) if p.isdigit() else p for p in re.split(r"(\d+)", str(text))]


def build_dashboard(session: Session, spec: dict, output: str | Path) -> Path:
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    data = {col: _column_payload(session.data[col]) for col in session.data.columns}
    quality = {
        "filas_originales": len(session.raw),
        "filas_finales": len(session.data),
        "problemas": [
            {k: v for k, v in i.items() if k in ("columna", "problema", "filas_afectadas")} for i in session.issues
        ],
        "limpieza": session.cleaning_log,
    }
    page = TEMPLATE
    replacements = {
        "__TITLE__": html.escape(spec.get("titulo") or "Dashboard"),
        "__SUBTITLE__": html.escape(spec.get("subtitulo") or ""),
        "__SOURCE__": html.escape(session.path.name),
        "__FOOTER__": html.escape(spec.get("pie") or "Dashboard generado por el agente de Proyecto-Web-Deep."),
        "__DATA__": _json_for_script(data),
        "__SPEC__": _json_for_script(spec),
        "__QUALITY__": _json_for_script(quality),
    }
    for key, value in replacements.items():
        page = page.replace(key, value)
    output.write_text(page, encoding="utf-8")
    return output


def _json_for_script(obj) -> str:
    # Evita que un texto del dataset cierre la etiqueta <script>
    return json.dumps(obj, ensure_ascii=False, default=str).replace("</", "<\\/")


TEMPLATE = r"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/plotly.js/2.35.2/plotly.min.js"></script>
<style>
:root {
  --bg: #f6f4f1; --panel: #ffffff; --ink: #1f2430; --muted: #5f6673; --line: #e3ded7;
  --accent: #9c4f2e; --accent-soft: #f3e3da; --s1: #9c4f2e; --s2: #2f6f8f; --s3: #6b8e3a; --s4: #b8862b; --s5: #7a5c99; --s6: #c25b6b;
}
@media (prefers-color-scheme: dark) {
  :root { --bg: #15171c; --panel: #1f232a; --ink: #eceae6; --muted: #a3a8b3; --line: #343a44;
    --accent: #e08a62; --accent-soft: #3a2a23; --s1: #e08a62; --s2: #6db3d6; --s3: #a3c76d; --s4: #e2b55a; --s5: #b394d6; --s6: #e88a99; }
}
* { box-sizing: border-box; }
body { margin: 0; font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; background: var(--bg); color: var(--ink); }
header { padding: 24px 16px 8px; max-width: 1280px; margin: 0 auto; }
h1 { margin: 0 0 4px; font-size: 1.6rem; }
header p { margin: 0; color: var(--muted); }
main { max-width: 1280px; margin: 0 auto; padding: 8px 16px 40px; display: grid; grid-template-columns: 260px 1fr; gap: 16px; }
@media (max-width: 860px) { main { grid-template-columns: 1fr; } }
aside, section.panel { background: var(--panel); border: 1px solid var(--line); border-radius: 12px; padding: 14px; }
aside { align-self: start; position: sticky; top: 12px; max-height: calc(100vh - 24px); overflow: auto; }
@media (max-width: 860px) { aside { position: static; max-height: none; } }
aside h2, section h2 { font-size: 1rem; margin: 0 0 10px; }
fieldset { border: 0; padding: 0; margin: 0 0 14px; }
legend { font-weight: 600; font-size: .85rem; margin-bottom: 6px; }
.chips { display: flex; flex-wrap: wrap; gap: 6px; }
.chips label { font-size: .8rem; border: 1px solid var(--line); border-radius: 999px; padding: 3px 9px; cursor: pointer; user-select: none; }
.chips input { position: absolute; opacity: 0; }
.chips label:has(input:checked) { background: var(--accent); border-color: var(--accent); color: #fff; }
.chips label:has(input:focus-visible) { outline: 2px solid var(--accent); outline-offset: 2px; }
.range { display: flex; gap: 6px; }
.range input { width: 100%; padding: 4px 6px; border: 1px solid var(--line); border-radius: 6px; background: var(--bg); color: var(--ink); }
button { font: inherit; border: 1px solid var(--accent); color: var(--accent); background: transparent; border-radius: 8px; padding: 6px 10px; cursor: pointer; width: 100%; }
.content { display: grid; gap: 16px; min-width: 0; }
.kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; }
.kpi { background: var(--panel); border: 1px solid var(--line); border-radius: 12px; padding: 12px 14px; }
.kpi .label { color: var(--muted); font-size: .8rem; }
.kpi .value { font-size: 1.7rem; font-weight: 700; font-variant-numeric: tabular-nums; }
.kpi .sub { color: var(--muted); font-size: .75rem; }
.charts { display: grid; grid-template-columns: repeat(auto-fit, minmax(420px, 1fr)); gap: 16px; }
@media (max-width: 520px) { .charts { grid-template-columns: 1fr; } }
.chart { min-width: 0; }
.chart .plot { height: 340px; }
.chart .plot.map { height: 460px; border-radius: 8px; overflow: hidden; }
.chart p { color: var(--muted); font-size: .85rem; margin: 6px 0 0; }
ul.findings { margin: 0; padding-left: 20px; } ul.findings li { margin-bottom: 6px; }
table { width: 100%; border-collapse: collapse; font-size: .82rem; }
th, td { text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--line); vertical-align: top; }
th { color: var(--muted); font-weight: 600; }
td.n { text-align: right; font-variant-numeric: tabular-nums; }
details summary { cursor: pointer; font-weight: 600; }
.count { color: var(--muted); font-size: .85rem; margin-bottom: 10px; }
footer { max-width: 1280px; margin: 0 auto; padding: 0 16px 30px; color: var(--muted); font-size: .8rem; }
</style>
</head>
<body>
<header>
  <h1>__TITLE__</h1>
  <p>__SUBTITLE__</p>
</header>
<main>
  <aside aria-label="Filtros">
    <h2>Filtros</h2>
    <div class="count" id="count"></div>
    <div id="filters"></div>
    <button type="button" id="reset">Quitar filtros</button>
  </aside>
  <div class="content">
    <div class="kpis" id="kpis"></div>
    <section class="panel" id="findings-panel" hidden>
      <h2>Hallazgos</h2>
      <ul class="findings" id="findings"></ul>
    </section>
    <div class="charts" id="charts"></div>
    <section class="panel">
      <details>
        <summary>Calidad del dato: problemas encontrados y cómo se han tratado</summary>
        <div id="quality"></div>
      </details>
    </section>
  </div>
</main>
<footer>Fuente: __SOURCE__ · __FOOTER__</footer>
<script>
const DATA = __DATA__;
const SPEC = __SPEC__;
const QUALITY = __QUALITY__;
const COLS = Object.keys(DATA);
const N = DATA[COLS[0]].v.length;
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const PALETTE = () => ["--s1","--s2","--s3","--s4","--s5","--s6"].map(css);
const fmt = (x, d = 0) => x == null || isNaN(x) ? "–" : x.toLocaleString("es-ES", {maximumFractionDigits: d, minimumFractionDigits: d});
const value = (col, i) => { const c = DATA[col], v = c.v[i]; return v == null ? null : c.t === "cat" ? c.c[v] : v; };

// ---------- Filtros ----------
const state = {};
function buildFilters() {
  const box = document.getElementById("filters");
  for (const col of SPEC.filtros || []) {
    const c = DATA[col]; if (!c) continue;
    const fs = document.createElement("fieldset");
    fs.innerHTML = `<legend>${col.replaceAll("_", " ")}</legend>`;
    if (c.t === "cat") {
      state[col] = {type: "cat", sel: new Set()};
      const chips = document.createElement("div"); chips.className = "chips";
      c.c.forEach((cat, idx) => {
        const lab = document.createElement("label");
        const inp = document.createElement("input"); inp.type = "checkbox";
        inp.addEventListener("change", () => { inp.checked ? state[col].sel.add(idx) : state[col].sel.delete(idx); render(); });
        lab.append(inp, document.createTextNode(cat)); chips.append(lab);
      });
      fs.append(chips);
    } else {
      const nums = c.t === "fecha" ? null : c.v.filter(v => v != null);
      state[col] = {type: c.t, min: null, max: null};
      const r = document.createElement("div"); r.className = "range";
      const type = c.t === "fecha" ? "date" : "number";
      const lo = Object.assign(document.createElement("input"), {type, "aria-label": `${col} desde`, placeholder: nums ? `${Math.min(...nums)}` : ""});
      const hi = Object.assign(document.createElement("input"), {type, "aria-label": `${col} hasta`, placeholder: nums ? `${Math.max(...nums)}` : ""});
      const parse = v => v === "" ? null : (c.t === "fecha" ? v : Number(v));
      lo.addEventListener("input", () => { state[col].min = parse(lo.value); render(); });
      hi.addEventListener("input", () => { state[col].max = parse(hi.value); render(); });
      r.append(lo, hi); fs.append(r);
    }
    box.append(fs);
  }
  document.getElementById("reset").addEventListener("click", () => {
    box.querySelectorAll("input").forEach(i => { i.checked = false; i.value = ""; });
    for (const s of Object.values(state)) { if (s.sel) s.sel.clear(); s.min = s.max = null; }
    render();
  });
}
function filteredRows() {
  const rows = [];
  outer: for (let i = 0; i < N; i++) {
    for (const [col, s] of Object.entries(state)) {
      const raw = DATA[col].v[i];
      if (s.type === "cat") { if (s.sel.size && !s.sel.has(raw)) continue outer; }
      else if (s.min != null || s.max != null) {
        if (raw == null) continue outer;
        if (s.min != null && raw < s.min) continue outer;
        if (s.max != null && raw > s.max) continue outer;
      }
    }
    rows.push(i);
  }
  return rows;
}

// ---------- Agregaciones ----------
function keyOf(chart, col, i) {
  const v = value(col, i);
  if (v == null) return null;
  if (chart.tramos && col === chart.x && typeof v === "number") return binLabel(chart.tramos, v);
  if (DATA[col].t === "fecha") return v.slice(0, 7);
  return v;
}
function binLabel(edges, v) {
  for (let k = 0; k < edges.length - 1; k++) if (v >= edges[k] && v < edges[k + 1]) return `${edges[k]}–${edges[k + 1]}`;
  return null;
}
function orderedKeys(chart, col, keys) {
  if (chart.tramos && col === chart.x) return chart.tramos.slice(0, -1).map((e, k) => `${e}–${chart.tramos[k + 1]}`).filter(k => keys.has(k));
  const c = DATA[col];
  if (c.t === "cat") return c.c.filter(k => keys.has(k));
  return [...keys].sort((a, b) => a < b ? -1 : a > b ? 1 : 0);
}
const hit = (chart, i) => { const v = value(chart.columna, i); return v == null ? null : String(v) === String(chart.valor); };

// ---------- Gráficos ----------
const baseLayout = () => ({
  margin: {l: 56, r: 16, t: 10, b: 60}, paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)",
  font: {family: "system-ui, sans-serif", color: css("--ink"), size: 12},
  xaxis: {gridcolor: css("--line"), automargin: true}, yaxis: {gridcolor: css("--line"), automargin: true, rangemode: "tozero"},
  legend: {orientation: "h", y: -0.25}, bargap: 0.25, hoverlabel: {font: {family: "system-ui"}},
});
function drawChart(chart, el, rows) {
  const L = baseLayout(), P = PALETTE(); let traces = [];
  if (chart.tipo === "mapa") return drawMap(chart, el, rows);
  if (chart.tipo === "histograma") {
    traces = [{type: "histogram", x: rows.map(i => DATA[chart.x].v[i]).filter(v => v != null), marker: {color: P[0]}, nbinsx: chart.intervalos || 40,
      hovertemplate: "%{x}<br>%{y} registros<extra></extra>"}];
    L.yaxis.title = {text: "registros"};
  } else if (chart.tipo === "calor") {
    const counts = new Map(), xs = new Set(), ys = new Set();
    for (const i of rows) {
      const a = keyOf(chart, chart.x, i), b = keyOf(chart, chart.y, i); if (a == null || b == null) continue;
      xs.add(a); ys.add(b); const k = a + "\u0000" + b;
      const c = counts.get(k) || {n: 0, h: 0}; c.n++; if (chart.columna && hit(chart, i)) c.h++; counts.set(k, c);
    }
    const X = orderedKeys(chart, chart.x, xs), Y = orderedKeys(chart, chart.y, ys);
    const rate = !!chart.columna;
    const z = Y.map(b => X.map(a => { const c = counts.get(a + "\u0000" + b); return !c ? null : rate ? (c.n >= 20 ? 100 * c.h / c.n : null) : c.n; }));
    traces = [{type: "heatmap", x: X, y: Y, z, colorscale: [[0, css("--panel")], [1, P[0]]], xgap: 2, ygap: 2,
      hovertemplate: `%{x} · %{y}<br>${rate ? "%{z:.1f}%" : "%{z} registros"}<extra></extra>`, colorbar: {thickness: 10}}];
    L.yaxis.rangemode = undefined;
  } else if (chart.tipo === "tasa") {
    const agg = new Map(), keys = new Set();
    const groupCol = chart.color;
    for (const i of rows) {
      const k = keyOf(chart, chart.x, i), h = hit(chart, i); if (k == null || h == null) continue;
      const g = groupCol ? value(groupCol, i) : "_"; if (g == null) continue;
      keys.add(k); const id = g + "\u0000" + k; const c = agg.get(id) || {n: 0, h: 0}; c.n++; if (h) c.h++; agg.set(id, c);
    }
    const X = orderedKeys(chart, chart.x, keys);
    const groups = groupCol ? orderedKeys({}, groupCol, new Set([...agg.keys()].map(k => k.split("\u0000")[0]))) : ["_"];
    traces = groups.map((g, gi) => {
      const cs = X.map(k => agg.get(g + "\u0000" + k) || {n: 0, h: 0});
      return {type: "bar", name: g === "_" ? "" : g, x: X, y: cs.map(c => c.n ? 100 * c.h / c.n : null), customdata: cs.map(c => c.n),
        marker: {color: P[gi % P.length]}, hovertemplate: `%{x}${g === "_" ? "" : " · " + g}<br>%{y:.1f}% (n=%{customdata})<extra></extra>`};
    });
    L.barmode = "group"; L.showlegend = !!groupCol;
    L.yaxis.title = {text: `% ${chart.columna.replaceAll("_", " ")} = ${chart.valor}`}; L.yaxis.ticksuffix = "%";
  } else { // barras y linea_tiempo
    const agg = new Map(), keys = new Set(); const groupCol = chart.color;
    for (const i of rows) {
      const k = keyOf(chart, chart.x, i); if (k == null) continue;
      const g = groupCol ? value(groupCol, i) : "_"; if (g == null) continue;
      keys.add(k); const id = g + "\u0000" + k; agg.set(id, (agg.get(id) || 0) + 1);
    }
    let X = orderedKeys(chart, chart.x, keys);
    const groups = groupCol ? orderedKeys({}, groupCol, new Set([...agg.keys()].map(k => k.split("\u0000")[0]))) : ["_"];
    if (chart.tipo === "barras" && !groupCol && DATA[chart.x].t === "cat" && !chart.orden_natural) X.sort((a, b) => (agg.get("_\u0000" + b) || 0) - (agg.get("_\u0000" + a) || 0));
    const line = chart.tipo === "linea_tiempo";
    const horizontal = !line && chart.horizontal;
    traces = groups.map((g, gi) => {
      const ys = X.map(k => agg.get(g + "\u0000" + k) || 0);
      const t = {type: line ? "scatter" : "bar", mode: line ? "lines" : undefined, name: g === "_" ? "" : g,
        marker: {color: P[gi % P.length]}, line: line ? {color: P[gi % P.length], width: 2} : undefined,
        hovertemplate: `%{${horizontal ? "y" : "x"}}${g === "_" ? "" : " · " + g}<br>%{${horizontal ? "x" : "y"}} registros<extra></extra>`};
      if (horizontal) { t.orientation = "h"; t.x = ys; t.y = X; } else { t.x = X; t.y = ys; }
      return t;
    });
    L.barmode = "stack"; L.showlegend = !!groupCol;
    if (horizontal) { L.yaxis.autorange = "reversed"; L.xaxis.title = {text: "registros"}; } else L.yaxis.title = {text: "registros"};
  }
  if (chart.color) L.legend.title = {text: chart.color.replaceAll("_", " ") + ": "};
  if (!(chart.tipo === "barras" && chart.horizontal)) L.xaxis.title = {text: (chart.x || "").replaceAll("_", " ")};
  if (chart.tipo === "calor") L.yaxis.title = {text: chart.y.replaceAll("_", " ")};
  Plotly.react(el, traces, L, {displaylogo: false, responsive: true});
}

// ---------- Mapa ----------
const MAX_POINTS = 20000;
function drawMap(chart, el, rows) {
  const P = PALETTE(), lat = DATA[chart.lat].v, lon = DATA[chart.lon].v;
  let pts = rows.filter(i => lat[i] != null && lon[i] != null);
  const total = pts.length;
  if (pts.length > MAX_POINTS) { const step = pts.length / MAX_POINTS; pts = Array.from({length: MAX_POINTS}, (_, k) => pts[Math.floor(k * step)]); }
  const groupCol = chart.color && DATA[chart.color].t === "cat" ? chart.color : null;
  const groups = groupCol ? DATA[groupCol].c : ["_"];
  const label = i => chart.etiqueta ? String(value(chart.etiqueta, i) ?? "") : "";
  const traces = groups.map((g, gi) => {
    const sel = groupCol ? pts.filter(i => value(groupCol, i) === g) : pts;
    return {type: "scattermap", mode: "markers", name: g === "_" ? "" : g,
      lat: sel.map(i => lat[i]), lon: sel.map(i => lon[i]), text: sel.map(label),
      marker: {size: total > 3000 ? 5 : 8, color: P[gi % P.length], opacity: 0.75},
      hovertemplate: `%{text}${g === "_" ? "" : "<br>" + g}<br>%{lat:.5f}, %{lon:.5f}<extra></extra>`};
  }).filter(t => t.lat.length);
  const view = mapView(pts.map(i => lat[i]), pts.map(i => lon[i]));
  const L = {margin: {l: 0, r: 0, t: 0, b: 0}, paper_bgcolor: "rgba(0,0,0,0)", showlegend: !!groupCol,
    legend: {orientation: "h", y: -0.02, yanchor: "top", title: groupCol ? {text: groupCol.replaceAll("_", " ") + ": "} : undefined},
    font: {family: "system-ui, sans-serif", color: css("--ink"), size: 12},
    map: {style: "open-street-map", center: view.center, zoom: view.zoom}};
  Plotly.react(el, traces, L, {displaylogo: false, responsive: true, scrollZoom: true});
  const note = el.parentElement.querySelector(".map-note");
  if (note) note.textContent = total > MAX_POINTS ? `Se muestran ${fmt(MAX_POINTS)} de ${fmt(total)} puntos.` : `${fmt(total)} puntos con coordenadas.`;
}
function mapView(lats, lons) {
  if (!lats.length) return {center: {lat: 40.4168, lon: -3.7038}, zoom: 10};
  const q = (a, p) => { const s = [...a].sort((x, y) => x - y); return s[Math.floor(p * (s.length - 1))]; };
  // Se ignoran el 1 % de puntos más alejados para que un dato raro no aleje el zoom
  const la0 = q(lats, .01), la1 = q(lats, .99), lo0 = q(lons, .01), lo1 = q(lons, .99);
  const span = Math.max(la1 - la0, (lo1 - lo0) * 0.6, 0.002);
  return {center: {lat: (la0 + la1) / 2, lon: (lo0 + lo1) / 2}, zoom: Math.max(1, Math.min(16, Math.log2(180 / span) - 0.3))};
}

// ---------- KPIs ----------
function kpiValue(k, rows) {
  if (k.tipo === "media") { const xs = rows.map(i => DATA[k.columna].v[i]).filter(v => v != null); return {v: fmt(xs.reduce((a, b) => a + b, 0) / xs.length, 1), sub: `${fmt(xs.length)} con dato`}; }
  if (k.tipo === "tasa") { let n = 0, h = 0; for (const i of rows) { const r = hit(k, i); if (r == null) continue; n++; if (r) h++; } return {v: fmt(n ? 100 * h / n : NaN, 1) + " %", sub: `${fmt(h)} de ${fmt(n)}`}; }
  return {v: fmt(rows.length), sub: `de ${fmt(N)} en total`};
}

// ---------- Render ----------
const chartEls = [];
function setup() {
  buildFilters();
  const box = document.getElementById("charts");
  for (const chart of SPEC.graficos || []) {
    const sec = document.createElement("section"); sec.className = "panel chart";
    sec.innerHTML = `<h2></h2><div class="plot" role="img"></div><p></p>`;
    sec.querySelector("h2").textContent = chart.titulo || "";
    sec.querySelector(".plot").setAttribute("aria-label", chart.titulo || "gráfico");
    sec.querySelector("p").textContent = chart.explicacion || "";
    if (chart.ancho_completo || chart.tipo === "mapa") sec.style.gridColumn = "1 / -1";
    if (chart.tipo === "mapa") {
      sec.querySelector(".plot").classList.add("map");
      const note = document.createElement("p"); note.className = "map-note"; sec.append(note);
    }
    box.append(sec); chartEls.push([chart, sec.querySelector(".plot")]);
  }
  const f = SPEC.hallazgos || [];
  if (f.length) { document.getElementById("findings-panel").hidden = false; document.getElementById("findings").innerHTML = ""; for (const t of f) { const li = document.createElement("li"); li.textContent = t; document.getElementById("findings").append(li); } }
  renderQuality();
  render();
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", render);
}
function render() {
  const rows = filteredRows();
  document.getElementById("count").textContent = `${fmt(rows.length)} de ${fmt(N)} registros`;
  const kb = document.getElementById("kpis"); kb.innerHTML = "";
  for (const k of SPEC.kpis || [{etiqueta: "Registros", tipo: "conteo"}]) {
    const r = kpiValue(k, rows); const d = document.createElement("div"); d.className = "kpi";
    d.innerHTML = `<div class="label"></div><div class="value"></div><div class="sub"></div>`;
    d.querySelector(".label").textContent = k.etiqueta; d.querySelector(".value").textContent = r.v; d.querySelector(".sub").textContent = r.sub;
    kb.append(d);
  }
  for (const [chart, el] of chartEls) drawChart(chart, el, rows);
}
function renderQuality() {
  const q = QUALITY, box = document.getElementById("quality");
  const esc = s => String(s ?? "").replace(/[&<>]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;"}[c]));
  let h = `<p>${fmt(q.filas_originales)} filas en el archivo original, ${fmt(q.filas_finales)} tras la limpieza.</p>`;
  h += `<h3>Problemas detectados</h3><table><thead><tr><th>Columna</th><th>Problema</th><th>Filas</th></tr></thead><tbody>`;
  for (const p of q.problemas) h += `<tr><td>${esc(p.columna)}</td><td>${esc(p.problema)}</td><td class="n">${fmt(p.filas_afectadas)}</td></tr>`;
  h += `</tbody></table><h3>Operaciones de limpieza aplicadas</h3><table><thead><tr><th>Operación</th><th>Columna</th><th>Detalle</th><th>Filas cambiadas</th></tr></thead><tbody>`;
  for (const o of q.limpieza) {
    const det = Object.entries(o).filter(([k]) => !["op", "columna", "filas_cambiadas"].includes(k)).map(([k, v]) => `${k}: ${typeof v === "object" ? JSON.stringify(v) : v}`).join(" · ");
    h += `<tr><td>${esc(o.op)}</td><td>${esc(o.columna || "")}</td><td>${esc(det)}</td><td class="n">${fmt(o.filas_cambiadas)}</td></tr>`;
  }
  box.innerHTML = h + "</tbody></table>";
}
setup();
</script>
</body>
</html>
"""
