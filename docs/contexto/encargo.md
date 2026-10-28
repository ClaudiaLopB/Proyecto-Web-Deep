# Encargo

> Lo fija el alumno. Es lo único que reciben el tester y el crítico de diseño además de la página.

## Caso

Observatorio municipal de seguridad vial. Conjunto de datos de accidentes de tráfico urbanos con atestado municipal (`datos/accidentes_urbanos.csv`, 9.200 registros, 16 campos) y su ficha (`datos/ficha_accidentes_urbanos.pdf`).

## Pregunta de negocio

El ayuntamiento tiene que decidir dónde pone el esfuerzo de la segunda mitad de su plan de seguridad vial. Las medidas candidatas responden a diagnósticos distintos:

1. **Velocidad**: ¿cuánto pesa la velocidad frente al resto de factores una vez que el accidente se ha producido? ¿Sigue siendo la palanca, o toca proteger al usuario vulnerable (peatón, ciclista, dos ruedas)?
2. **Intersecciones frente a tramos**: ¿qué ocurre en las intersecciones? (inversión en glorietas frente a plataforma única).
3. **Entorno**: ¿qué aportan la visibilidad, el estado del firme y el alumbrado? (competencia de otras áreas municipales).

## Requisitos del entregable

- R1. Una página web (`web/index.html`) que se abre en el navegador sin instalar nada.
- R2. Responde a las tres preguntas con gráficos; junto a cada gráfico, una frase de negocio que diga qué mirar.
- R3. Filtros que actualizan a la vez todos los indicadores y gráficos.
- R4. Cada cifra que aparece se puede rehacer desde el CSV con la limpieza documentada.
- R5. Explica qué problemas de calidad tenía el dato y qué se hizo con cada uno.
- R6. Se lee bien en el móvil (unos 400 px de ancho) y en modo oscuro.
- R7. Las conclusiones son prudentes: asociaciones, no causas, y mencionan las limitaciones del dato.
