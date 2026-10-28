# Análisis

> Lo escribe el data scientist. Primera versión: la del plan `ejemplos/accidentes_plan.json`.
> Cifras calculadas con `agente.datos.query` sobre el dato limpio (tasas sin contar los 43 nulos de `con_lesiones`).

## 1. ¿Cuánto pesa la velocidad?

- Gráfico: tasa de accidentes con heridos por tramos de velocidad (0-20-30-40-50-60-80-200 km/h), desglosada por usuario vulnerable.
- Cifras: 5,6 % (<20 km/h, n=1.529) → 47,8 % (50-60, n=788) → 75,1 % (≥80, n=205).
- Con usuario vulnerable: 49,5 % (n=2.802) frente a 17,7 % sin él (n=6.355). Entre 30 y 50 km/h: 60,1 % frente a 17,6 %.
- El límite señalizado no separa: 27,9 % / 26,7 % / 28,4 % para 30 / 50 / 70.
- Limitación: velocidad estimada en el atestado, sin revisión; 518 sin dato.
- Gráfico nuevo (pestaña Velocidad): tasa con heridos por límite señalizado, desglosada por usuario vulnerable.
  - Sin vulnerable: 18,3 % (30 km/h, n=3.056), 16,8 % (50, n=2.595), 18,9 % (70, n=677).
  - Con vulnerable: 49,9 % (30, n=1.336), 48,1 % (50, n=1.203), 53,5 % (70, n=254).
  - La velocidad media estimada tampoco cambia con el límite: 36,3 / 35,2 / 35,6 km/h (n=4.163 / 3.597 / 884). Con este dato, el límite señalizado no se asocia ni a la velocidad del impacto ni a la gravedad.
  - 41 filas sin límite y 43 sin `con_lesiones` quedan fuera.

## 2. Intersecciones frente a tramos

- Gráfico: tasa con heridos por tipo de accidente, desglosada por intersección.
- Cifras: 29,2 % en intersección (n=3.903) frente a 26,2 % (n=5.254). Con vulnerable: 53,3 % frente a 46,6 %.
- Gráfico nuevo (pestaña Intersecciones, el primero): tasa con heridos según intersección, desglosada por usuario vulnerable.
  - Sin vulnerable: 18,5 % en intersección (n=2.701) frente a 17,2 % en tramo (n=3.654).
  - Con vulnerable: 53,3 % en intersección (n=1.202) frente a 46,6 % en tramo (n=1.600).
  - La proporción de accidentes con vulnerable es la misma dentro y fuera (30,8 % frente a 30,5 %), así que la diferencia no viene de que haya más vulnerables en las intersecciones.
- Por tipo (gráfico existente): la intersección suma de 0 a 5 puntos; la mayor diferencia, en alcances (23,4 %, n=1.361, frente a 18,4 %, n=1.769); en salida de vía, ninguna (26,4 % frente a 26,3 %).

## 3. Entorno

- Gráficos: tasa con heridos por estado del firme, alumbrado y tramos de visibilidad.
- Firme: 35,3 % deslizante (n=385), 31,4 % mojado, 25,9 % seco. Alumbrado y visibilidad: diferencias de 1-4 puntos.

## Pestañas del dashboard

Orden de lo más a lo menos decisivo para la decisión del ayuntamiento. Filtros, KPI, hallazgos y panel de calidad quedan fuera de las pestañas.

| # | Pestaña | Pregunta | Gráficos, en orden |
|---|---|---|---|
| 1 | Velocidad | ¿Sigue siendo la velocidad la palanca, o toca proteger al usuario vulnerable? | velocidad del impacto × vulnerable; límite señalizado × vulnerable (nuevo) |
| 2 | Intersecciones | ¿Se asocian las intersecciones a más gravedad, y para quién? | intersección × vulnerable (nuevo); tipo × intersección |
| 3 | Entorno | ¿Qué aportan firme, alumbrado y visibilidad? | firme; alumbrado; visibilidad |
| 4 | Dónde y cuándo | Contexto descriptivo | volumen por tipo; calor tipo × distrito; evolución mensual |

- Velocidad: los dos gráficos se leen juntos; la velocidad real separa la gravedad y el límite señalizado no, y en ambos la brecha del usuario vulnerable es de unos 30 puntos.
- Intersecciones: primero la respuesta global (solo hay diferencia con vulnerables), luego el desglose por tipo para ver dónde se nota.
- Entorno: los tres factores de otras áreas municipales, con la misma métrica para compararlos; el firme primero porque es el único que separa.
- Dónde y cuándo: volumen, reparto y tiempo; no responde a ninguna pregunta por sí solo, por eso va al final.

## Fuera del análisis

- `atestado_policial`: se arrastra del sistema de origen (diario, trampa 9).
- `edad_conductor`: se consolida mensualmente; solo descriptiva.
