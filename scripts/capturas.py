"""Hace capturas de la página para el crítico de diseño: escritorio y móvil, en claro y oscuro.

Uso: python scripts/capturas.py web/index.html [--salida salida/capturas]
Requiere: pip install -r requirements-dev.txt && python -m playwright install chromium
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

VIEWS = [("escritorio", 1300, 900), ("movil", 400, 860)]
THEMES = ["light", "dark"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("pagina", type=Path)
    parser.add_argument("--salida", type=Path, default=Path("salida/capturas"))
    args = parser.parse_args()
    args.salida.mkdir(parents=True, exist_ok=True)
    url = args.pagina.resolve().as_uri()

    with sync_playwright() as p:
        # CHROMIUM_PATH permite usar un Chromium ya instalado en el sistema
        browser = p.chromium.launch(executable_path=os.environ.get("CHROMIUM_PATH") or None)
        errors: list[str] = []
        for name, width, height in VIEWS:
            for theme in THEMES:
                page = browser.new_page(viewport={"width": width, "height": height}, color_scheme=theme)
                page.on("pageerror", lambda e: errors.append(str(e)))
                page.goto(url)
                page.wait_for_timeout(2500)  # da tiempo a Plotly a dibujar
                out = args.salida / f"{name}_{'claro' if theme == 'light' else 'oscuro'}.png"
                page.screenshot(path=str(out), full_page=True)
                print(f"📸 {out}")
                page.close()
        browser.close()
    if errors:
        print("⚠️  Errores en la página:\n- " + "\n- ".join(sorted(set(errors))))


if __name__ == "__main__":
    main()
