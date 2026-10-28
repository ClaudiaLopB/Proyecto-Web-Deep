# Contrato compartido

> Lo leen extractor, data scientist, backend y frontend. El tester y el crítico **no** lo leen.
> Si cambias algo de aquí, dilo en tu respuesta al orquestador para que avise a los demás.

## Dueños de los archivos

| Archivo | Dueño | Los demás |
|---|---|---|
| `datos/*` | extractor | solo leen |
| `docs/contexto/diario_trampas.md` | extractor | solo leen |
| `docs/contexto/analisis.md`, `ejemplos/*_plan.json` | data scientist | solo leen |
| `agente/datos.py` (limpieza, perfil, consultas) | backend | solo leen |
| `agente/dashboard.py` (plantilla HTML, CSS y JS de la página) | frontend | solo leen |
| `agente/agente.py`, `agente/automatico.py`, `agente/__main__.py` | backend | — |
| `tests/` | quien cambie el código, sobre su parte | — |
| `web/index.html` | **nadie a mano**: se genera con `python -m agente ... --salida web/index.html` | — |
| `CLAUDE.md`, `docs/contexto/encargo.md` | orquestador / alumno | — |

## Esquema de datos tras la limpieza

Lo mantiene el extractor (tipos) y el backend (limpieza). Una fila = un accidente.

| Campo | Tipo | Valores / unidades |
|---|---|---|
| `fecha` | fecha | dd/mm/aaaa en origen |
| `tipo_accidente` | categoría | alcance, atropello, caída de dos ruedas, colisión lateral, salida de vía |
| `velocidad_estimada_kmh` | número | km/h; nulo si no consta |
| `implicado_vulnerable`, `uso_proteccion`, `interseccion`, `con_lesiones`, `atestado_policial` | sí / no | |
| `estado_firme` | categoría | seco, mojado, deslizante |
| `visibilidad_m` | número | metros |
| `edad_conductor` | número | años |
| `hora` | número | 0-23 |
| `distrito` | categoría | distrito 1 … distrito 11 |
| `vehiculos_implicados` | número | 1-4 |
| `limite_velocidad_kmh` | número | 30, 50, 70 |
| `alumbrado` | categoría | día, noche con alumbrado, noche sin alumbrado |

## Contrato del plan (JSON)

El data scientist escribe el plan; el backend lo ejecuta y el frontend lo pinta. Formato de `ejemplos/<caso>_plan.json`:

```json
{
  "limpieza": [ {"op": "a_nulo|normalizar_categorias|rango_valido|fecha|descartar_columna|quitar_duplicados",
                 "columna": "...", "motivo": "...", "...": "parámetros de la operación"} ],
  "dashboard": {
    "titulo": "...", "subtitulo": "...", "pie": "...",
    "filtros": ["columna", "..."],
    "kpis": [ {"etiqueta": "...", "tipo": "conteo|media|tasa", "columna": "...", "valor": "..."} ],
    "graficos": [ {"tipo": "barras|tasa|histograma|linea_tiempo|calor", "titulo": "...",
                   "x": "...", "y": "...", "color": "...", "columna": "...", "valor": "...",
                   "tramos": [0, 30, 50], "horizontal": false, "ancho_completo": false,
                   "explicacion": "la frase de negocio: la escribe el data scientist, la coloca el frontend"} ],
    "hallazgos": ["frases con cifras obtenidas con agente.datos.query"]
  }
}
```

Dentro de la página, el backend vuelca los datos limpios como `DATA` (columnas codificadas), el plan como `SPEC` y el registro de limpieza como `QUALITY`. Toda la agregación que depende de los filtros la hace el JS del frontend sobre `DATA`.
