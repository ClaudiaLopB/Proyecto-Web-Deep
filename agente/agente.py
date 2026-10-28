"""Agente de IA (Claude) que convierte un CSV en un dashboard interactivo.

El agente trabaja con herramientas deterministas (pandas) y nunca calcula cifras
"de memoria": perfila el dato, decide la limpieza, consulta agregados para
redactar los hallazgos y por último diseña el dashboard.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

import anthropic
from anthropic import beta_tool

from . import datos
from .dashboard import build_dashboard, validate_spec

MODEL = "claude-opus-5-5"

SYSTEM_PROMPT = """Eres un analista de datos. Tu trabajo es convertir un conjunto de datos en un dashboard \
interactivo útil para que una persona que toma decisiones entienda el dato y pueda explorarlo.

Trabaja siempre con las herramientas; no inventes ni estimes cifras. Un buen orden es:
1. `perfilar_dataset` y `detectar_problemas` para entender columnas, tipos y calidad del dato.
2. Si hay documentación de contexto (una ficha del dataset), úsala para saber qué preguntas de negocio \
importan y qué campos son poco fiables o se rellenan después del hecho.
3. `limpiar` con la lista completa de operaciones que decidas (cada llamada parte del dato original). \
Justifica cada operación en `motivo`. Los valores centinela (p. ej. -99) y los imposibles se pasan a nulo, \
no se borran filas.
4. `consultar` para calcular los agregados que respondan a las preguntas de negocio. Cada hallazgo que \
escribas debe apoyarse en una cifra que hayas obtenido aquí, con el tamaño de muestra cuando sea pequeño.
5. `crear_dashboard` con la especificación final. Si devuelve errores, corrígelos y vuelve a llamarla.

Criterios para el dashboard:
- Pocos KPI (3-5) y entre 5 y 9 gráficos, cada uno con una `explicacion` de una frase que diga qué mirar.
- Prefiere tasas (`tipo: "tasa"`) a conteos cuando la pregunta es de riesgo o gravedad: un conteo alto puede \
deberse solo a que hay más casos de ese tipo.
- Si `perfilar_dataset` encuentra coordenadas (latitud/longitud), incluye un gráfico `mapa` al principio.
- Usa `tramos` para agrupar variables numéricas continuas en las tasas y mapas de calor.
- Los filtros deben ser las dimensiones por las que alguien querría segmentar (zona, tipo, condiciones).
- Los hallazgos (4-7) son frases concretas, prudentes (correlación no es causalidad) y que mencionen las \
limitaciones de calidad del dato cuando afecten a la conclusión.
Escribe todo en español. Al terminar, resume en pocas líneas qué has hecho."""


def run_agent(session: datos.Session, output: Path, goal: str | None = None,
              context_file: Path | None = None, verbose: bool = True) -> dict | None:
    """Ejecuta el agente. Devuelve la especificación del dashboard creado, o None si no llegó a crearlo."""
    result: dict = {}

    @beta_tool
    def perfilar_dataset() -> str:
        """Devuelve el perfil del dataset original: filas, columnas, tipo inferido de cada columna, ausencias,
        estadísticos de las numéricas y valores más frecuentes de las categóricas."""
        return json.dumps(datos.profile(session), ensure_ascii=False, default=str)

    @beta_tool
    def detectar_problemas() -> str:
        """Busca problemas de calidad del dato (categorías mal escritas, valores centinela, valores imposibles,
        textos que significan 'sin dato', fechas como texto, duplicados) y propone una operación para cada uno."""
        return json.dumps(datos.detect_issues(session), ensure_ascii=False, default=str)

    @beta_tool
    def limpiar(operaciones: list[dict]) -> str:
        """Aplica una lista de operaciones de limpieza sobre el dato ORIGINAL (cada llamada sustituye a la anterior).

        Args:
            operaciones: Lista ordenada de operaciones. Cada una es un objeto con "op", "columna" (salvo
                quitar_duplicados) y "motivo". Tipos: {"op": "a_nulo", "valores": [...]} pasa esos valores a nulo;
                {"op": "normalizar_categorias"} unifica mayúsculas, tildes y espacios; {"op": "rango_valido",
                "min": n|null, "max": n|null} pasa a nulo lo que queda fuera; {"op": "fecha", "formato": "%d/%m/%Y"};
                {"op": "descartar_columna"}; {"op": "quitar_duplicados"}.
        """
        if not session.issues:
            datos.detect_issues(session)
        log = datos.apply_operations(session, operaciones)
        result["limpieza"] = operaciones
        return json.dumps({"registro": log, "filas": len(session.data)}, ensure_ascii=False, default=str)

    @beta_tool
    def consultar(agrupar_por: list[str], metrica: str = "conteo", columna: str | None = None,
                  valor: str | None = None, tramos: dict | None = None) -> str:
        """Calcula un agregado sobre el dato limpio (llama antes a `limpiar`).

        Args:
            agrupar_por: Columnas por las que agrupar (lista vacía para el total). Las fechas se agrupan por mes.
            metrica: "conteo", "media" (de `columna`) o "tasa" (% de filas donde `columna` == `valor`, sin contar nulos).
            columna: Columna sobre la que se calcula la media o la tasa.
            valor: Valor que cuenta como acierto en la tasa, p. ej. "sí".
            tramos: Opcional. Cortes para agrupar columnas numéricas, p. ej. {"velocidad_kmh": [0, 30, 50, 200]}.
        """
        return json.dumps(datos.query(session, agrupar_por, metrica, columna, valor, tramos), ensure_ascii=False, default=str)

    @beta_tool
    def crear_dashboard(especificacion: dict) -> str:
        """Genera el dashboard HTML interactivo a partir del dato limpio. Devuelve errores si la especificación no es válida.

        Args:
            especificacion: Objeto con "titulo", "subtitulo", "filtros" (columnas), "kpis" (lista de
                {"etiqueta", "tipo": "conteo"|"media"|"tasa", "columna", "valor"}), "graficos" (lista de
                {"tipo": "barras"|"tasa"|"histograma"|"linea_tiempo"|"calor"|"mapa", "titulo", "x", "y" (solo calor),
                "lat", "lon", "etiqueta" (solo mapa: columnas de latitud, longitud y texto al pasar el ratón),
                "color" (columna para desglosar, opcional), "columna" y "valor" (para tasas o calor de tasas),
                "tramos" (cortes numéricos de x, opcional), "horizontal" (bool), "ancho_completo" (bool),
                "explicacion"}) y "hallazgos" (lista de frases).
        """
        errors = validate_spec(session, especificacion)
        if errors:
            return json.dumps({"ok": False, "errores": errors}, ensure_ascii=False)
        path = build_dashboard(session, especificacion, output)
        result["spec"] = especificacion
        # El plan se guarda para poder regenerar el mismo dashboard sin IA (--spec)
        plan = {"limpieza": result.get("limpieza", []), "dashboard": especificacion}
        output.with_suffix(".plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
        return json.dumps({"ok": True, "archivo": str(path)}, ensure_ascii=False)

    content: list[dict] = []
    if context_file:
        content += _context_blocks(context_file)
    task = f"Convierte el archivo «{session.path.name}» ({len(session.raw)} filas) en un dashboard interactivo."
    if goal:
        task += f"\nObjetivo de la persona usuaria: {goal}"
    if context_file:
        task += "\nTienes arriba la documentación del dataset."
    content.append({"type": "text", "text": task})

    client = anthropic.Anthropic()
    runner = client.beta.messages.tool_runner(
        model=MODEL,
        max_tokens=32000,
        system=SYSTEM_PROMPT,
        thinking={"type": "adaptive"},
        output_config={"effort": "high"},
        # Si el modelo declina la petición, la API la reintenta con otro modelo adecuado
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        tools=[perfilar_dataset, detectar_problemas, limpiar, consultar, crear_dashboard],
        messages=[{"role": "user", "content": content}],
        max_iterations=40,
    )
    for message in runner:
        if verbose:
            _print_progress(message)
        if message.stop_reason == "refusal":
            print("El modelo ha rechazado la petición.")
            break
    return result.get("spec")


def _context_blocks(path: Path) -> list[dict]:
    """La documentación del dataset va como documento: PDF en base64 o texto plano."""
    if path.suffix.lower() == ".pdf":
        data = base64.standard_b64encode(path.read_bytes()).decode()
        return [{"type": "document", "title": path.name,
                 "source": {"type": "base64", "media_type": "application/pdf", "data": data}}]
    return [{"type": "document", "title": path.name,
             "source": {"type": "text", "media_type": "text/plain", "data": path.read_text(encoding="utf-8")}}]


def _print_progress(message) -> None:
    for block in message.content:
        if block.type == "text" and block.text.strip():
            print(f"\n🤖 {block.text.strip()}")
        elif block.type == "tool_use":
            print(f"   → {block.name}")
