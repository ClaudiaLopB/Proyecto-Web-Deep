# Diario de trampas del dato

> Lo escribe el extractor. Cada trampa: qué es, cuántas filas, cómo se detecta y qué propone hacer.
> Primera versión a partir de la exploración inicial de `datos/accidentes_urbanos.csv`.

| # | Campo | Trampa | Filas | Propuesta |
|---|---|---|---|---|
| 1 | `tipo_accidente` | 18 variantes para 5 tipos: mayúsculas, sin tildes y espacios sobrantes | 2.300 | normalizar categorías |
| 2 | `velocidad_estimada_kmh` | `-99` = no consta (centinela); además el dato es una estimación del atestado sin revisión manual | 518 | pasar a nulo; avisar en las conclusiones |
| 3 | `visibilidad_m` | Valores imposibles (hasta 143.000 m) | 3 | pasar a nulo por encima de un máximo razonable |
| 4 | `edad_conductor` | Edades imposibles (hasta 54.000 años); la ficha dice que se consolida mensualmente | 2 | rango válido 14-100 |
| 5 | `con_lesiones` | "si" sin tilde (el resto de columnas usa "sí") y 43 vacíos | 2.514 + 43 | normalizar; los vacíos fuera de las tasas |
| 6 | `alumbrado` | `N/D` = sin dato, más 33 vacíos | 455 + 33 | pasar a nulo |
| 7 | `fecha` | Texto dd/mm/aaaa, 42 vacíos | 42 | convertir a fecha |
| 8 | `hora`, `vehiculos_implicados`, `limite_velocidad_kmh` | Vacíos sueltos | 36 / 41 / 41 | dejar nulos |
| 9 | `atestado_policial` | La ficha dice que se arrastra sin cambios del sistema de origen: no informa sobre el accidente | — | no usar como factor explicativo |
