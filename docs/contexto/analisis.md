# Análisis

> Lo escribe el data scientist. Primera versión: la del plan `ejemplos/accidentes_plan.json`.
> Cifras calculadas con `agente.datos.query` sobre el dato limpio (tasas sin contar los 43 nulos de `con_lesiones`).

## 1. ¿Cuánto pesa la velocidad?

- Gráfico: tasa de accidentes con heridos por tramos de velocidad (0-20-30-40-50-60-80-200 km/h), desglosada por usuario vulnerable.
- Cifras: 5,6 % (<20 km/h, n=1.529) → 47,8 % (50-60, n=788) → 75,1 % (≥80, n=205).
- Con usuario vulnerable: 49,5 % (n=2.802) frente a 17,7 % sin él (n=6.355). Entre 30 y 50 km/h: 60,1 % frente a 17,6 %.
- El límite señalizado no separa: 27,9 % / 26,7 % / 28,4 % para 30 / 50 / 70.
- Limitación: velocidad estimada en el atestado, sin revisión; 518 sin dato.

## 2. Intersecciones frente a tramos

- Gráfico: tasa con heridos por tipo de accidente, desglosada por intersección.
- Cifras: 29,2 % en intersección (n=3.903) frente a 26,2 % (n=5.254). Con vulnerable: 53,3 % frente a 46,6 %.

## 3. Entorno

- Gráficos: tasa con heridos por estado del firme, alumbrado y tramos de visibilidad.
- Firme: 35,3 % deslizante (n=385), 31,4 % mojado, 25,9 % seco. Alumbrado y visibilidad: diferencias de 1-4 puntos.

## Fuera del análisis

- `atestado_policial`: se arrastra del sistema de origen (diario, trampa 9).
- `edad_conductor`: se consolida mensualmente; solo descriptiva.
