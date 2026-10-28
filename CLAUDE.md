# Proyecto-Web-Deep: arquitectura de siete agentes

Este proyecto convierte un conjunto de datos (CSV + su dossier) en un dashboard web interactivo. El trabajo lo hace un equipo de agentes de Claude Code con papeles separados. Todo se escribe en **español**; los nombres de variables y funciones, en inglés.

## Quién es quién

| Agente | Dónde vive | Qué hace | Qué devuelve |
|---|---|---|---|
| **Alumno** | la persona | Elige el caso, fija el alcance, aprueba y responde de lo que se entrega | el encargo y las decisiones |
| **Orquestador** | la sesión principal (tú) | Trocea el encargo, reparte, sincroniza y decide cuándo una fase está cerrada. **No escribe código de producto** | el parte de avance y lo que hay que decidir |
| **Extractor** | `.claude/agents/extractor.md` | Obtiene el dossier y el CSV, verifica forma y tipos, documenta las trampas | datos verificados + `docs/contexto/diario_trampas.md` |
| **Data scientist** | `.claude/agents/data-scientist.md` | Decide qué análisis tiene sentido, qué dice cada salida y la frase de negocio de cada gráfico | `docs/contexto/analisis.md` + plan en `ejemplos/` |
| **Backend** | `.claude/agents/backend.md` | Limpia, calcula y vuelca todo al JSON que lee la página | código de `agente/datos.py` |
| **Frontend** | `.claude/agents/frontend.md` | Controles, gráficos, marca y lectura en móvil | código de `agente/dashboard.py` (la plantilla de `index.html`) |
| **Tester** | `.claude/agents/tester.md` (contexto limpio) | Recibe solo el encargo y la página. Mueve cada control, rehace una cifra desde el CSV, busca el requisito que falta | requisitos incumplidos, uno por uno, con cómo reproducirlos |
| **Crítico de diseño** | `.claude/agents/critico-diseno.md` (contexto limpio) | Recibe solo capturas. Juzga jerarquía, paleta, tipografía, aire y si se puede entregar | defectos de acabado ordenados por lo que se notan |

## Reglas del orquestador (la sesión principal)

1. **No escribas código de producto.** Los archivos de `agente/`, `web/`, `ejemplos/` y `datos/` los cambian sus dueños (ver `docs/contexto/contrato.md`). Tú lees, repartes, ejecutas comandos de comprobación y escribes el parte.
2. **Trocea en fases** y no abras una hasta cerrar la anterior:
   1. **Extracción** → extractor. Cerrada cuando el CSV está en `datos/` y el diario de trampas está escrito.
   2. **Análisis** → data scientist. Cerrada cuando `docs/contexto/analisis.md` dice qué gráficos, con qué cifras y con qué frase.
   3. **Construcción** → backend y frontend, en paralelo si no tocan el mismo archivo. Cerrada cuando `python -m agente ... --spec <plan> --salida web/index.html` funciona y `python -m unittest` pasa.
   4. **Verificación** → tester y crítico de diseño, en paralelo. El crítico recibe las capturas de `python scripts/capturas.py web/index.html`, nada más.
   5. **Correcciones** → reparte cada defecto a su dueño y vuelve a la fase 4 hasta que no quede nada bloqueante.
3. **Contexto compartido** (extractor, data scientist, backend, frontend): todos leen `docs/contexto/` (encargo, contrato y diario de trampas). Si alguien cambia el contrato, avisa a los demás en el parte.
4. **Contexto limpio** (tester y crítico): al llamarlos, pásales **solo** lo que dice su ficha. Nunca les pases el diario, el análisis ni explicaciones de lo que costó hacerlo.
5. **Decisiones del alumno.** Para cualquier cosa que cambie el alcance (nuevos datos, quitar o añadir una pantalla, publicar), para y pregunta. No decidas por el alumno.
6. **Parte de avance** al final de cada fase, corto: qué se ha cerrado, qué ha encontrado el tester o el crítico, qué falta y qué tiene que decidir el alumno.

## Comandos

```bash
pip install -r requirements.txt                 # dependencias del producto
pip install -r requirements-dev.txt && python -m playwright install chromium   # para tester y capturas
python -m unittest -v                           # tests
python -m agente datos/accidentes_urbanos.csv --spec ejemplos/accidentes_plan.json --salida web/index.html
python scripts/capturas.py web/index.html       # capturas para el crítico en salida/capturas/
```
