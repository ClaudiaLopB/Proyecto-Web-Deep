"""Modo sin IA: limpieza y diseño del dashboard con reglas fijas.

Sirve para ejecutar el proyecto sin clave de API y como red de seguridad si el
agente falla. El resultado es correcto pero genérico: no hay hallazgos.
"""

from __future__ import annotations

import pandas as pd

from .datos import Session, normalize_key

# Palabras que suelen indicar la variable "resultado" en un dataset
TARGET_HINTS = ("lesion", "herid", "grave", "muert", "fallec", "victim", "resultado", "objetivo", "target")


def automatic_operations(session: Session) -> list[dict]:
    """Aplica todas las propuestas de limpieza detectadas, una sola vez cada una."""
    ops, seen = [], set()
    for issue in session.issues:
        op = issue.get("propuesta")
        if not op:
            continue
        key = repr(sorted(op.items(), key=lambda kv: kv[0]))
        if key not in seen:
            seen.add(key)
            ops.append({**op, "motivo": issue["problema"]})
    # Los centinelas primero, para que no distorsionen el cálculo de rangos
    order = {"a_nulo": 0, "normalizar_categorias": 1, "rango_valido": 2, "fecha": 3, "quitar_duplicados": 4}
    return sorted(ops, key=lambda o: order.get(o["op"], 9))


def _is_text(series: pd.Series) -> bool:
    return not (pd.api.types.is_numeric_dtype(series) or pd.api.types.is_datetime64_any_dtype(series))


def _yes_no(df: pd.DataFrame, col: str) -> bool:
    values = df[col].dropna()
    return set(values.map(normalize_key).unique()) <= {"si", "no"} and len(values) > 0


def automatic_spec(session: Session) -> dict:
    df = session.data
    categorical = [c for c in df.columns if _is_text(df[c]) and 1 < df[c].nunique() <= 15]
    numeric = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    dates = [c for c in df.columns if pd.api.types.is_datetime64_any_dtype(df[c])]
    binary = [c for c in categorical if _yes_no(df, c)]
    target = next((c for c in binary if any(h in c.lower() for h in TARGET_HINTS)), binary[0] if binary else None)
    yes = None
    if target:
        yes = next(v for v in df[target].dropna().unique() if normalize_key(v) == "si")

    kpis = [{"etiqueta": "Registros", "tipo": "conteo"}]
    if target:
        kpis.append({"etiqueta": f"% {target.replace('_', ' ')}", "tipo": "tasa", "columna": target, "valor": yes})
    for col in [b for b in binary if b != target][:2]:
        kpis.append({"etiqueta": f"% {col.replace('_', ' ')}", "tipo": "tasa", "columna": col, "valor": yes or "sí"})
    for col in numeric[:1]:
        kpis.append({"etiqueta": f"Media {col.replace('_', ' ')}", "tipo": "media", "columna": col})

    charts = []
    if dates:
        charts.append({"tipo": "linea_tiempo", "titulo": f"Registros por mes ({dates[0]})", "x": dates[0], "ancho_completo": True})
    multi = [c for c in categorical if c not in binary]
    for col in multi[:3]:
        charts.append({"tipo": "barras", "titulo": f"Registros por {col.replace('_', ' ')}", "x": col, "horizontal": df[col].nunique() > 6})
    if target:
        for col in [c for c in categorical if c != target][:3]:
            charts.append({"tipo": "tasa", "titulo": f"% {target.replace('_', ' ')} según {col.replace('_', ' ')}", "x": col, "columna": target, "valor": yes})
    for col in numeric[:3]:
        charts.append({"tipo": "histograma", "titulo": f"Distribución de {col.replace('_', ' ')}", "x": col})

    return {
        "titulo": f"Dashboard de {session.path.stem.replace('_', ' ')}",
        "subtitulo": "Generado en modo automático (sin IA): limpieza y gráficos por reglas fijas.",
        "filtros": (dates[:1] + multi[:3] + binary[:4] + numeric[:2]),
        "kpis": kpis,
        "graficos": charts,
        "hallazgos": [],
    }
