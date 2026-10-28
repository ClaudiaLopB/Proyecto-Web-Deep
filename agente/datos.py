"""Carga, perfilado, detección de problemas de calidad y limpieza de un CSV.

Todo es genérico: no hay nada específico del dataset de accidentes. El agente
(o el modo automático) decide qué operaciones de limpieza aplicar.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

# Textos que en la práctica significan "dato ausente"
NULL_TOKENS = {"", "n/d", "nd", "na", "n/a", "nan", "null", "none", "-", "?", "sin dato", "desconocido"}
# Valores centinela típicos en registros operativos (p. ej. -99 = "no consta")
SENTINELS = {-1, -9, -99, -999, -9999, 99, 999, 9999, 99999}
DATE_FORMATS = ["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d", "%d/%m/%y"]
MAX_CATEGORIES = 30


def normalize_key(value: str) -> str:
    """Clave para agrupar variantes de una misma categoría: sin espacios extra, minúsculas y sin tildes."""
    text = " ".join(str(value).split()).lower()
    text = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def _is_null_token(value: str) -> bool:
    return normalize_key(value) in NULL_TOKENS


@dataclass
class Session:
    """Estado compartido entre las herramientas del agente."""

    path: Path
    raw: pd.DataFrame
    data: pd.DataFrame
    types: dict[str, str] = field(default_factory=dict)
    issues: list[dict] = field(default_factory=list)
    cleaning_log: list[dict] = field(default_factory=list)
    context: str = ""


def load_csv(path: str | Path) -> Session:
    path = Path(path)
    raw = pd.read_csv(path, dtype=str, keep_default_na=False, sep=None, engine="python", encoding="utf-8-sig")
    raw.columns = [c.strip() for c in raw.columns]
    session = Session(path=path, raw=raw, data=raw.copy())
    session.types = {c: infer_type(raw[c]) for c in raw.columns}
    return session


def infer_type(series: pd.Series) -> str:
    values = series[~series.map(_is_null_token)].str.strip()
    if values.empty:
        return "texto"
    numeric = pd.to_numeric(values.str.replace(",", ".", regex=False), errors="coerce")
    if numeric.notna().mean() >= 0.95:
        return "numerica"
    for fmt in DATE_FORMATS:
        if pd.to_datetime(values, format=fmt, errors="coerce").notna().mean() >= 0.95:
            return "fecha"
    n_keys = values.map(normalize_key).nunique()
    if n_keys <= MAX_CATEGORIES or n_keys <= 0.05 * len(values):
        return "categorica"
    return "texto"


def _date_format(series: pd.Series) -> str | None:
    values = series[~series.map(_is_null_token)].str.strip()
    best, best_ok = None, 0.0
    for fmt in DATE_FORMATS:
        ok = pd.to_datetime(values, format=fmt, errors="coerce").notna().mean()
        if ok > best_ok:
            best, best_ok = fmt, ok
    return best


def _to_number(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series.astype(str).str.strip().str.replace(",", ".", regex=False), errors="coerce")


def profile(session: Session) -> dict:
    """Resumen del dataset en bruto: tipos, ausencias, estadísticos y categorías."""
    df = session.raw
    columns = []
    for col in df.columns:
        s = df[col]
        nulls = int(s.map(_is_null_token).sum())
        info: dict = {"columna": col, "tipo": session.types[col], "ausentes": nulls}
        if session.types[col] == "numerica":
            x = _to_number(s)
            info.update(
                {
                    "min": _r(x.min()),
                    "q1": _r(x.quantile(0.25)),
                    "mediana": _r(x.median()),
                    "q3": _r(x.quantile(0.75)),
                    "max": _r(x.max()),
                    "media": _r(x.mean()),
                    "valores_distintos": int(x.nunique()),
                }
            )
        elif session.types[col] in ("categorica", "texto"):
            vc = s.value_counts()
            info["valores_distintos"] = int(len(vc))
            info["mas_frecuentes"] = {k: int(v) for k, v in vc.head(12).items()}
        else:
            fmt = _date_format(s)
            dates = pd.to_datetime(s, format=fmt, errors="coerce")
            info.update({"formato": fmt, "desde": str(dates.min().date()), "hasta": str(dates.max().date())})
        columns.append(info)
    return {
        "archivo": session.path.name,
        "filas": len(df),
        "columnas": len(df.columns),
        "filas_duplicadas": int(df.duplicated().sum()),
        "detalle": columns,
    }


def detect_issues(session: Session) -> list[dict]:
    """Busca problemas típicos de calidad y propone una operación de limpieza para cada uno."""
    df = session.raw
    issues: list[dict] = []
    yes_no_columns = []
    for col in df.columns:
        s = df[col]
        kind = session.types[col]
        tokens = sorted({v for v in s.unique() if _is_null_token(v) and v != ""})
        if tokens:
            n = int(s.isin(tokens).sum())
            issues.append(
                {
                    "columna": col,
                    "problema": f"Valores que significan 'sin dato' escritos como texto: {tokens}",
                    "filas_afectadas": n,
                    "propuesta": {"op": "a_nulo", "columna": col, "valores": tokens},
                }
            )
        if kind == "categorica":
            values = s[~s.map(_is_null_token)]
            groups = values.groupby(values.map(normalize_key)).agg(lambda g: sorted(set(g)))
            messy = {k: v for k, v in groups.items() if len(v) > 1}
            if messy:
                affected = int((values != _normalize_categories(values, _yes_no_canonical(df))).sum())
                issues.append(
                    {
                        "columna": col,
                        "problema": "La misma categoría aparece escrita de varias formas (mayúsculas, tildes, espacios)",
                        "variantes": {k: v for k, v in list(messy.items())[:8]},
                        "categorias_reales": int(len(groups)),
                        "categorias_aparentes": int(values.nunique()),
                        "filas_afectadas": affected,
                        "propuesta": {"op": "normalizar_categorias", "columna": col},
                    }
                )
            keys = set(groups.index)
            if keys and keys <= {"si", "no"}:
                yes_no_columns.append((col, sorted(set(values))))
        if kind == "numerica":
            x = _to_number(s)
            x = x[x.notna()]
            counts = x.value_counts()
            for sentinel in SENTINELS:
                n = int(counts.get(float(sentinel), 0))
                others = x[x != sentinel]
                if n >= max(5, 0.005 * len(x)) and (others.min() >= 0 > sentinel or others.max() < sentinel):
                    issues.append(
                        {
                            "columna": col,
                            "problema": f"Valor centinela {sentinel} repetido {n} veces: parece un código de 'no consta', no una medida",
                            "filas_afectadas": n,
                            "propuesta": {"op": "a_nulo", "columna": col, "valores": [sentinel]},
                        }
                    )
            clean = x[~x.isin(SENTINELS)]
            q1, q3 = clean.quantile(0.25), clean.quantile(0.75)
            iqr = max(q3 - q1, 1e-9)
            upper = q3 + 20 * iqr
            extreme = clean[clean > upper]
            if len(extreme):
                issues.append(
                    {
                        "columna": col,
                        "problema": "Valores imposibles o extremadamente atípicos (más de 20 rangos intercuartílicos sobre Q3)",
                        "ejemplos": sorted({_r(v) for v in extreme})[:8],
                        "filas_afectadas": int(len(extreme)),
                        "propuesta": {"op": "rango_valido", "columna": col, "min": None, "max": _r(upper)},
                    }
                )
        if kind == "fecha":
            issues.append(
                {
                    "columna": col,
                    "problema": "Fecha guardada como texto",
                    "filas_afectadas": int((~s.map(_is_null_token)).sum()),
                    "propuesta": {"op": "fecha", "columna": col, "formato": _date_format(s)},
                }
            )
        nulls = int((s.str.strip() == "").sum())
        if nulls:
            issues.append(
                {
                    "columna": col,
                    "problema": f"{nulls} celdas vacías ({nulls / len(s):.1%})",
                    "filas_afectadas": nulls,
                    "propuesta": None,
                }
            )
    # Coherencia entre columnas sí/no: unas usan "sí" y otras "si"
    spellings = {tuple(v) for _, v in yes_no_columns}
    if len(spellings) > 1:
        for col, values in yes_no_columns:
            if "si" in values:
                issues.append(
                    {
                        "columna": col,
                        "problema": f"Usa {values} mientras otras columnas sí/no usan 'sí'",
                        "filas_afectadas": int((df[col] == "si").sum()),
                        "propuesta": {"op": "normalizar_categorias", "columna": col},
                    }
                )
    if int(df.duplicated().sum()):
        issues.append(
            {
                "columna": "(todas)",
                "problema": "Filas duplicadas",
                "filas_afectadas": int(df.duplicated().sum()),
                "propuesta": {"op": "quitar_duplicados"},
            }
        )
    session.issues = issues
    return issues


def apply_operations(session: Session, operations: list[dict]) -> list[dict]:
    """Aplica operaciones de limpieza sobre una copia del dato en bruto y registra el efecto de cada una."""
    df = session.raw.copy()
    log: list[dict] = []
    yes_no_canonical = _yes_no_canonical(df)
    for op in operations:
        kind, col = op.get("op"), op.get("columna")
        reason = op.get("motivo", "")
        if col is not None and col not in df.columns:
            log.append({"op": kind, "columna": col, "error": "columna inexistente"})
            continue
        before = df[col].copy() if col else None
        if kind == "a_nulo":
            targets = {normalize_key(str(v)) for v in op.get("valores", [])}
            numeric_targets = {float(v) for v in op.get("valores", []) if _is_float(v)}
            as_num = _to_number(df[col])
            mask = df[col].map(normalize_key).isin(targets) | as_num.isin(numeric_targets)
            df.loc[mask, col] = ""
        elif kind == "normalizar_categorias":
            df[col] = _normalize_categories(df[col], yes_no_canonical)
        elif kind == "rango_valido":
            x = _to_number(df[col])
            mask = pd.Series(False, index=df.index)
            if op.get("min") is not None:
                mask |= x < float(op["min"])
            if op.get("max") is not None:
                mask |= x > float(op["max"])
            df.loc[mask, col] = ""
        elif kind == "fecha":
            pass  # se convierte al final, ver más abajo
        elif kind == "descartar_columna":
            df = df.drop(columns=[col])
            log.append({"op": kind, "columna": col, "motivo": reason, "filas_cambiadas": len(df)})
            continue
        elif kind == "quitar_duplicados":
            n = len(df)
            df = df.drop_duplicates()
            log.append({"op": kind, "motivo": reason, "filas_cambiadas": n - len(df)})
            continue
        else:
            log.append({"op": kind, "error": "operación desconocida"})
            continue
        changed = int((before != df[col]).sum())
        entry = {k: v for k, v in op.items() if k not in ("op", "columna")}
        log.append({"op": kind, "columna": col, **entry, "filas_cambiadas": changed})
    session.data = _typed(df, session.types, operations)
    session.cleaning_log = log
    return log


def _typed(df: pd.DataFrame, types: dict[str, str], operations: list[dict]) -> pd.DataFrame:
    """Convierte cada columna a su tipo final (número, fecha o texto con nulos reales)."""
    date_formats = {o["columna"]: o.get("formato") for o in operations if o.get("op") == "fecha"}
    out = pd.DataFrame(index=df.index)
    for col in df.columns:
        s = df[col].where(~df[col].map(_is_null_token), None)
        if types.get(col) == "numerica":
            out[col] = _to_number(s)
        elif types.get(col) == "fecha":
            out[col] = pd.to_datetime(s, format=date_formats.get(col) or _date_format(df[col]), errors="coerce")
        else:
            out[col] = pd.Series([None if pd.isna(v) else " ".join(str(v).split()) for v in s], index=s.index, dtype=object)
    return out.reset_index(drop=True)


def _yes_no_canonical(df: pd.DataFrame) -> str:
    """Si alguna columna escribe 'sí' con tilde, esa es la forma correcta para todas."""
    for col in df.columns:
        if (df[col] == "sí").any():
            return "sí"
    return "si"


def _normalize_categories(series: pd.Series, yes: str) -> pd.Series:
    stripped = series.map(lambda v: " ".join(str(v).split()))
    keys = stripped.map(normalize_key)
    canonical = {}
    for key, group in stripped.groupby(keys):
        if key == "":
            canonical[key] = ""
        elif key == "si":
            canonical[key] = yes
        else:
            # Forma preferida: en minúsculas y con tildes si alguna variante las tiene
            lower = group.str.lower()
            with_accents = lower[lower != lower.map(normalize_key)]
            canonical[key] = (with_accents if len(with_accents) else lower).value_counts().index[0]
    return keys.map(canonical)


def _is_float(value) -> bool:
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def _r(value) -> float | None:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    return round(float(value), 2)


def _fmt_edge(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else str(value)


def query(session: Session, group_by: list[str], metric: str = "conteo", column: str | None = None,
          value: str | None = None, bins: dict[str, list[float]] | None = None, limit: int = 40) -> dict:
    """Agregación simple sobre el dato limpio: conteo, media o tasa (% de filas con columna == valor)."""
    df = session.data.copy()
    for col, edges in (bins or {}).items():
        labels = [f"{_fmt_edge(a)}–{_fmt_edge(b)}" for a, b in zip(edges, edges[1:])]
        df[col] = pd.cut(df[col], bins=edges, right=False, labels=labels)
    for col in group_by:
        if col not in df.columns:
            return {"error": f"columna inexistente: {col}"}
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].dt.to_period("M").astype(str)
    grouped = df.groupby(group_by, dropna=True, observed=True) if group_by else None
    if metric == "conteo":
        table = grouped.size().rename("n") if grouped is not None else pd.Series({"total": len(df)}, name="n")
        result = table.to_frame()
    elif metric == "media":
        if grouped is None:
            return {"media": _r(df[column].mean()), "n": int(df[column].notna().sum())}
        result = grouped[column].agg(["mean", "count"]).rename(columns={"mean": "media", "count": "n"})
    elif metric == "tasa":
        valid = df[df[column].notna()]
        hit = valid[column].astype(str) == str(value)
        if not group_by:
            return {"tasa_%": _r(100 * hit.mean()), "n": int(len(valid))}
        result = hit.groupby([valid[c] for c in group_by], observed=True).agg(["mean", "count"])
        result = result.rename(columns={"mean": "tasa_%", "count": "n"})
        result["tasa_%"] = 100 * result["tasa_%"]
    else:
        return {"error": f"métrica desconocida: {metric}"}
    result = result.reset_index().round(2).head(limit)
    return {"filas": result.to_dict(orient="records")}
