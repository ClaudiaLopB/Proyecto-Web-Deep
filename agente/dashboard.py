"""Genera un dashboard HTML interactivo (un único archivo) a partir del dato limpio y una especificación.

La especificación es un diccionario que puede escribir el agente de IA o el modo automático:

{
  "titulo": str, "subtitulo": str,
  "filtros": [columna, ...],
  "kpis": [{"etiqueta": str, "tipo": "conteo" | "media" | "tasa", "columna": str, "valor": str}],
  "graficos": [{"tipo": "barras" | "tasa" | "histograma" | "linea_tiempo" | "calor",
                "titulo": str, "x": str, "y": str, "color": str,
                "columna": str, "valor": str, "tramos": [números], "explicacion": str,
                "pestana": str (opcional, nombre de una de "pestanas")}],
  "pestanas": [{"nombre": str, "descripcion": str}]  (opcional; sin ella no hay barra de pestañas),
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

CHART_TYPES = {"barras", "tasa", "histograma", "linea_tiempo", "calor"}


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
        for key in ("x", "y", "color", "columna"):
            if chart.get(key) and chart[key] not in cols:
                errors.append(f"gráfico '{chart.get('titulo')}': columna inexistente '{chart[key]}' en '{key}'")
        if chart.get("tipo") == "tasa" and not (chart.get("columna") and chart.get("valor") is not None):
            errors.append(f"gráfico '{chart.get('titulo')}': una tasa necesita 'columna' y 'valor'")
    tabs = spec.get("pestanas") or []
    names = [t.get("nombre") for t in tabs if isinstance(t, dict)]
    if len(names) != len(tabs) or not all(names):
        errors.append("pestanas: cada pestaña necesita un 'nombre'")
    if len(set(names)) != len(names):
        errors.append("pestanas: hay nombres de pestaña repetidos")
    for chart in spec.get("graficos", []):
        tab = chart.get("pestana")
        if tab and tab not in names:
            errors.append(f"gráfico '{chart.get('titulo')}': la pestaña '{tab}' no está en 'pestanas'")
    if not spec.get("graficos"):
        errors.append("el dashboard necesita al menos un gráfico")
    return errors


def _column_payload(series: pd.Series) -> dict:
    """Codifica una columna de forma compacta: categorías como índices, números tal cual."""
    if pd.api.types.is_datetime64_any_dtype(series):
        return {"t": "fecha", "v": [None if pd.isna(v) else v.strftime("%Y-%m-%d") for v in series]}
    if pd.api.types.is_numeric_dtype(series):
        return {"t": "num", "v": [None if pd.isna(v) else (int(v) if float(v).is_integer() else round(float(v), 2)) for v in series]}
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
        "__TABS__": _tabs_html(spec),
        "__DATA__": _json_for_script(data),
        "__SPEC__": _json_for_script(spec),
        "__QUALITY__": _json_for_script(quality),
    }
    for key, value in replacements.items():
        page = page.replace(key, value)
    output.write_text(page, encoding="utf-8")
    return output


def _tabs_html(spec: dict) -> str:
    """Barra de pestañas y un panel por pestaña; sin 'pestanas', una sola rejilla de gráficos (como antes).

    El JS coloca cada gráfico en el panel de su pestaña y gestiona la selección, el teclado y el hash.
    """
    tabs = [t for t in spec.get("pestanas") or [] if isinstance(t, dict) and t.get("nombre")]
    if not tabs:
        return '<div class="charts"></div>'
    buttons, panels = [], []
    for k, tab in enumerate(tabs):
        name = html.escape(tab["nombre"])
        selected = "true" if k == 0 else "false"
        buttons.append(
            f'<button type="button" class="tab" role="tab" id="tab-{k}" aria-controls="panel-{k}" '
            f'aria-selected="{selected}" tabindex="{0 if k == 0 else -1}" data-nombre="{name}">{name}</button>'
        )
        panels.append(
            f'<div class="tabpanel" role="tabpanel" id="panel-{k}" aria-labelledby="tab-{k}" tabindex="0"'
            f'{"" if k == 0 else " hidden"}><p class="tab-desc">{html.escape(tab.get("descripcion") or "")}</p>'
            f'<div class="charts"></div></div>'
        )
    return (
        '<div class="tablist" role="tablist" aria-label="Secciones del análisis">' + "".join(buttons) + "</div>"
        + "".join(panels)
    )


def _json_for_script(obj) -> str:
    # Evita que un texto del dataset cierre la etiqueta <script>
    return json.dumps(obj, ensure_ascii=False, default=str).replace("</", "<\\/")


TEMPLATE = r"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/plotly.js/2.35.3/plotly.min.js"></script>
<style>
/* Paleta del observatorio.
   --accent: chips, botones y pestaña activa; también la serie única de los gráficos.
   --yes / --no: series sí/no (el valor que importa en color fuerte, "no" en gris apagado).
   --seq0 → --seq1: escala secuencial de un solo tono para el mapa de calor (arranca en un tono visible).
   --c1…--c6: series con más de dos categorías. */
:root {
  --bg: #eef1f5; --panel: #ffffff; --ink: #15202e; --muted: #4a5667; --line: #d5dce5;
  --accent: #1d5fa8; --on-accent: #ffffff; --accent-soft: #e4edf8;
  --yes: #c4314b; --no: #848f9e;
  --seq0: #c8daf0; --seq1: #0f3a73;
  --c1: #1d5fa8; --c2: #0d857c; --c3: #b0670a; --c4: #6c4fb0; --c5: #4a5667; --c6: #c4314b;
}
@media (prefers-color-scheme: dark) {
  :root { --bg: #0e1319; --panel: #17202b; --ink: #e6ebf1; --muted: #a9b4c2; --line: #2d3948;
    --accent: #78a8ec; --on-accent: #0b1422; --accent-soft: #1d2e45;
    --yes: #f26d7d; --no: #66727f;
    --seq0: #2a4266; --seq1: #b3d0ff;
    --c1: #78a8ec; --c2: #4cc2b5; --c3: #e3a54d; --c4: #b69cf0; --c5: #a9b4c2; --c6: #f26d7d; }
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
.chips label:has(input:checked) { background: var(--accent); border-color: var(--accent); color: var(--on-accent); }
.chips label:has(input:focus-visible) { outline: 2px solid var(--accent); outline-offset: 2px; }
.range { display: flex; gap: 6px; }
.range input { width: 100%; padding: 4px 6px; border: 1px solid var(--line); border-radius: 6px; background: var(--bg); color: var(--ink); }
button { font: inherit; border: 1px solid var(--accent); color: var(--accent); background: transparent; border-radius: 8px; padding: 6px 10px; cursor: pointer; width: 100%; }
button:hover { background: var(--accent-soft); }
button:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.tabs { min-width: 0; }
.tablist { display: flex; gap: 4px; overflow-x: auto; overscroll-behavior-x: contain; border-bottom: 1px solid var(--line); scrollbar-width: thin; padding: 2px 2px 0; }
.tablist .tab { flex: 0 0 auto; width: auto; white-space: nowrap; border: 0; border-bottom: 3px solid transparent; border-radius: 8px 8px 0 0;
  color: var(--muted); background: transparent; padding: 10px 14px 9px; font-weight: 600; font-size: .92rem; }
.tablist .tab:hover { color: var(--ink); background: var(--accent-soft); }
.tablist .tab[aria-selected="true"] { color: var(--accent); border-bottom-color: var(--accent); background: var(--accent-soft); }
.tablist .tab:focus-visible { outline: 2px solid var(--accent); outline-offset: -2px; }
.tab-desc { margin: 12px 0 14px; font-size: .95rem; }
.tabpanel:focus-visible { outline: 2px solid var(--accent); outline-offset: 4px; border-radius: 8px; }
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
    <div class="tabs" id="charts">__TABS__</div>
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
const CATS = () => ["--c1","--c2","--c3","--c4","--c5","--c6"].map(css);
// Colores de las series: sí/no siempre igual (sí fuerte, no apagado); serie única en el acento; resto, paleta categórica.
function seriesColors(groups) {
  if (groups.length === 1 && groups[0] === "_") return [css("--accent")];
  if (groups.every(g => g === "sí" || g === "no")) return groups.map(g => css(g === "sí" ? "--yes" : "--no"));
  const P = CATS(); return groups.map((g, k) => P[k % P.length]);
}
// Nombre de columna legible: guiones bajos fuera y tildes que faltan en los nombres técnicos.
const WORDS = {limite: "límite", vehiculos: "vehículos", kmh: "(km/h)", m: "(m)"};
const human = col => String(col || "").split("_").map(w => WORDS[w] || w.replace(/cion$/, "ción")).join(" ");
const slug = t => String(t || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
const fmt = (x, d = 0) => x == null || isNaN(x) ? "–" : x.toLocaleString("es-ES", {maximumFractionDigits: d, minimumFractionDigits: d});
const value = (col, i) => { const c = DATA[col], v = c.v[i]; return v == null ? null : c.t === "cat" ? c.c[v] : v; };

// ---------- Filtros ----------
const state = {};
function buildFilters() {
  const box = document.getElementById("filters");
  for (const col of SPEC.filtros || []) {
    const c = DATA[col]; if (!c) continue;
    const fs = document.createElement("fieldset");
    fs.innerHTML = `<legend></legend>`; fs.querySelector("legend").textContent = human(col);
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
  const L = baseLayout(); let traces = [];
  if (chart.tipo === "histograma") {
    traces = [{type: "histogram", x: rows.map(i => DATA[chart.x].v[i]).filter(v => v != null), marker: {color: css("--accent")}, nbinsx: chart.intervalos || 40,
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
    traces = [{type: "heatmap", x: X, y: Y, z, colorscale: [[0, css("--seq0")], [1, css("--seq1")]], xgap: 2, ygap: 2,
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
    const colors = seriesColors(groups);
    traces = groups.map((g, gi) => {
      const cs = X.map(k => agg.get(g + "\u0000" + k) || {n: 0, h: 0});
      return {type: "bar", name: g === "_" ? "" : g, x: X, y: cs.map(c => c.n ? 100 * c.h / c.n : null), customdata: cs.map(c => c.n),
        marker: {color: colors[gi]}, hovertemplate: `%{x}${g === "_" ? "" : " · " + g}<br>%{y:.1f}% (n=%{customdata})<extra></extra>`};
    });
    L.barmode = "group"; L.showlegend = !!groupCol;
    L.yaxis.title = {text: `% ${human(chart.columna)} = ${chart.valor}`}; L.yaxis.ticksuffix = "%";
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
    const colors = seriesColors(groups);
    traces = groups.map((g, gi) => {
      const ys = X.map(k => agg.get(g + "\u0000" + k) || 0);
      const t = {type: line ? "scatter" : "bar", mode: line ? "lines" : undefined, name: g === "_" ? "" : g,
        marker: {color: colors[gi]}, line: line ? {color: colors[gi], width: 2} : undefined,
        hovertemplate: `%{${horizontal ? "y" : "x"}}${g === "_" ? "" : " · " + g}<br>%{${horizontal ? "x" : "y"}} registros<extra></extra>`};
      if (horizontal) { t.orientation = "h"; t.x = ys; t.y = X; } else { t.x = X; t.y = ys; }
      return t;
    });
    L.barmode = "stack"; L.showlegend = !!groupCol;
    if (horizontal) { L.yaxis.autorange = "reversed"; L.xaxis.title = {text: "registros"}; } else L.yaxis.title = {text: "registros"};
  }
  if (chart.color) L.legend.title = {text: human(chart.color) + ": "};
  if (!(chart.tipo === "barras" && chart.horizontal)) L.xaxis.title = {text: human(chart.x)};
  if (chart.tipo === "calor") L.yaxis.title = {text: human(chart.y)};
  // Números sin tramos (p. ej. límite 30/50/70) en barras y tasas: categorías, no eje continuo
  if ((chart.tipo === "tasa" || chart.tipo === "barras") && !chart.tramos && DATA[chart.x] && DATA[chart.x].t === "num") L[chart.tipo === "barras" && chart.horizontal ? "yaxis" : "xaxis"].type = "category";
  Plotly.react(el, traces, L, {displaylogo: false, responsive: true});
}

// ---------- KPIs ----------
function kpiValue(k, rows) {
  if (k.tipo === "media") { const xs = rows.map(i => DATA[k.columna].v[i]).filter(v => v != null); return {v: fmt(xs.reduce((a, b) => a + b, 0) / xs.length, 1), sub: `${fmt(xs.length)} con dato`}; }
  if (k.tipo === "tasa") { let n = 0, h = 0; for (const i of rows) { const r = hit(k, i); if (r == null) continue; n++; if (r) h++; } return {v: fmt(n ? 100 * h / n : NaN, 1) + " %", sub: `${fmt(h)} de ${fmt(n)}`}; }
  return {v: fmt(rows.length), sub: `de ${fmt(N)} en total`};
}

// ---------- Render ----------
const chartEls = [];
const TAB_BTNS = [...document.querySelectorAll("#charts .tab")];
const TAB_PANELS = [...document.querySelectorAll("#charts .tabpanel")];
let activeTab = 0, lastRows = [];
function gridFor(chart) {
  if (!TAB_PANELS.length) return document.querySelector("#charts .charts");
  const k = TAB_BTNS.findIndex(b => b.dataset.nombre === chart.pestana);
  return TAB_PANELS[k < 0 ? 0 : k].querySelector(".charts");  // sin pestaña (o desconocida): a la primera
}
const tabOf = grid => TAB_PANELS.length ? TAB_PANELS.findIndex(p => p.contains(grid)) : 0;
function tabFromHash() {
  const m = /(?:^#|&)pestana=([^&]*)/.exec(location.hash); if (!m) return null;
  let v; try { v = decodeURIComponent(m[1]); } catch (e) { v = m[1]; }
  const k = TAB_BTNS.findIndex(b => slug(b.dataset.nombre) === slug(v));
  return k < 0 ? null : k;
}
function showTab(k, {focus = false, hash = true} = {}) {
  if (!TAB_BTNS.length) return;
  activeTab = k;
  TAB_BTNS.forEach((b, j) => { b.setAttribute("aria-selected", j === k ? "true" : "false"); b.tabIndex = j === k ? 0 : -1; });
  TAB_PANELS.forEach((p, j) => { p.hidden = j !== k; });
  if (focus) { TAB_BTNS[k].focus(); TAB_BTNS[k].scrollIntoView({block: "nearest", inline: "nearest"}); }
  if (hash) history.replaceState(null, "", "#pestana=" + slug(TAB_BTNS[k].dataset.nombre));
  // Plotly mide mal en contenedores ocultos: se dibuja (o se redimensiona) al mostrar la pestaña
  for (const e of chartEls) if (e.tab === k) { if (e.dirty) { drawChart(e.chart, e.el, lastRows); e.dirty = false; } else Plotly.Plots.resize(e.el); }
}
function setupTabs() {
  if (!TAB_BTNS.length) return;
  TAB_BTNS.forEach((b, k) => b.addEventListener("click", () => showTab(k)));
  document.querySelector("#charts .tablist").addEventListener("keydown", ev => {
    const n = TAB_BTNS.length, cur = Math.max(0, TAB_BTNS.indexOf(ev.target)), moves = {ArrowRight: cur + 1, ArrowLeft: cur - 1 + n, Home: 0, End: n - 1};
    if (!(ev.key in moves)) return;
    ev.preventDefault(); showTab(moves[ev.key] % n, {focus: true});
  });
  window.addEventListener("hashchange", () => { const k = tabFromHash(); if (k != null && k !== activeTab) showTab(k, {hash: false}); });
  const k = tabFromHash();
  if (k != null) showTab(k, {hash: false});
}
function setup() {
  buildFilters();
  setupTabs();
  for (const chart of SPEC.graficos || []) {
    const sec = document.createElement("section"); sec.className = "panel chart";
    sec.innerHTML = `<h2></h2><div class="plot" role="img"></div><p></p>`;
    sec.querySelector("h2").textContent = chart.titulo || "";
    sec.querySelector(".plot").setAttribute("aria-label", chart.titulo || "gráfico");
    sec.querySelector("p").textContent = chart.explicacion || "";
    if (chart.ancho_completo) sec.style.gridColumn = "1 / -1";
    const grid = gridFor(chart); grid.append(sec);
    chartEls.push({chart, el: sec.querySelector(".plot"), tab: tabOf(grid), dirty: true});
  }
  const f = SPEC.hallazgos || [];
  if (f.length) { document.getElementById("findings-panel").hidden = false; document.getElementById("findings").innerHTML = ""; for (const t of f) { const li = document.createElement("li"); li.textContent = t; document.getElementById("findings").append(li); } }
  renderQuality();
  render();
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", render);
}
function render() {
  const rows = lastRows = filteredRows();
  document.getElementById("count").textContent = `${fmt(rows.length)} de ${fmt(N)} registros`;
  const kb = document.getElementById("kpis"); kb.innerHTML = "";
  for (const k of SPEC.kpis || [{etiqueta: "Registros", tipo: "conteo"}]) {
    const r = kpiValue(k, rows); const d = document.createElement("div"); d.className = "kpi";
    d.innerHTML = `<div class="label"></div><div class="value"></div><div class="sub"></div>`;
    d.querySelector(".label").textContent = k.etiqueta; d.querySelector(".value").textContent = r.v; d.querySelector(".sub").textContent = r.sub;
    kb.append(d);
  }
  // Se dibujan los gráficos visibles; los de otras pestañas quedan pendientes hasta que se muestren
  for (const e of chartEls) { if (!TAB_PANELS.length || e.tab === activeTab) { drawChart(e.chart, e.el, rows); e.dirty = false; } else e.dirty = true; }
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
