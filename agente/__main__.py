"""Uso: python -m agente DATOS.csv [--contexto FICHA.pdf] [--objetivo "..."] [--salida dashboard.html] [--sin-ia | --spec plan.json]"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import datos
from .automatico import automatic_operations, automatic_spec
from .dashboard import build_dashboard, validate_spec


def main(argv: list[str] | None = None) -> int:
    # La consola de Windows usa cp1252 y no puede imprimir emojis: forzamos UTF-8.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(prog="agente", description="Convierte un CSV en un dashboard interactivo.")
    parser.add_argument("csv", type=Path, help="archivo CSV de entrada")
    parser.add_argument("--contexto", type=Path, help="documentación del dataset (PDF o texto) para el agente")
    parser.add_argument("--objetivo", help="qué quieres entender con el dashboard")
    parser.add_argument("--salida", type=Path, default=Path("salida/dashboard.html"))
    parser.add_argument("--spec", type=Path, help="especificación JSON ya hecha (limpieza + dashboard); no usa IA")
    parser.add_argument("--sin-ia", action="store_true", help="no usar Claude: limpieza y diseño por reglas fijas")
    args = parser.parse_args(argv)

    session = datos.load_csv(args.csv)
    print(f"📄 {args.csv.name}: {len(session.raw)} filas, {len(session.raw.columns)} columnas")

    use_ai = not args.sin_ia
    if use_ai and not args.spec and not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        print("⚠️  No hay ANTHROPIC_API_KEY: se usa el modo automático (sin IA).")
        use_ai = False

    spec = None
    if args.spec:
        plan = json.loads(args.spec.read_text(encoding="utf-8"))
        datos.detect_issues(session)
        datos.apply_operations(session, plan["limpieza"])
        errors = validate_spec(session, plan["dashboard"])
        if errors:
            print("❌ Especificación no válida:\n- " + "\n- ".join(errors))
            return 1
        spec = plan["dashboard"]
        build_dashboard(session, spec, args.salida)
        use_ai = False
    if use_ai:
        from .agente import run_agent

        spec = run_agent(session, args.salida, goal=args.objetivo, context_file=args.contexto)
        if spec is None:
            print("⚠️  El agente no llegó a crear el dashboard: se usa el modo automático.")
    if spec is None:
        datos.detect_issues(session)
        datos.apply_operations(session, automatic_operations(session))
        build_dashboard(session, automatic_spec(session), args.salida)

    print(f"✅ Dashboard: {args.salida.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
