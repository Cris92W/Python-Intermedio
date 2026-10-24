# Revisión del guion: Qwen3.8 contra el informe

Fuente: informe «Incendio de Chichas 2026» (PRACTICA_1). Guion original de Qwen3.8 en `guion_qwen_original.txt`; versión revisada en `guion.json`.

## Primer intento: Qwen comentó en lugar de escribir el guion

Qwen recibió solo la lista de datos, sin la instrucción, y respondió con un comentario sobre el análisis. En ese texto agregó afirmaciones que el informe no respalda:

| Lo que escribió Qwen | Qué dice el informe |
|---|---|
| «Pastoreo de camélidos», «regulación hídrica» | No se mencionan. |
| «Impacto profundo y de muy lenta recuperación» | El 85 % del área tuvo severidad baja. |
| «Riesgo social inminente», «amenaza directa» | Solo hay distancias de OpenStreetMap; no se evaluaron daños. |
| «Crisis de los incendios forestales» | Es pajonal altoandino, no bosque. |

## Segundo intento: correcciones al guion

| Escena | Qwen escribió | Corregí a | Por qué |
|---|---|---|---|
| 1 | «detecté el primer foco» | «un satélite detecta el primer foco» | Lo detectó el satélite NOAA-20 (VIIRS); yo analicé los datos después. |
| 3 | «El área se triplicó: mil seiscientas cuarenta y siete hectáreas» | «Al día siguiente, el área se triplicó; para el veinte sumaba mil seiscientas cuarenta y siete hectáreas» | Mezclaba dos datos: se triplicó del 17 al 18 (433 → 1 439 ha) y llegó a 1 647 ha el 20. |
| 4 | «Ochenta y cinco por ciento fue severidad baja … entre tres mil trescientos y cuatro mil cien metros» | «El ochenta y cinco por ciento fue de severidad baja … metros de altitud» | Faltaba decir de qué es el porcentaje y que los metros son de altitud. |
| 5 | «El borde quedó a cien metros» | «El borde quemado quedó a cien metros» | Más claro; la distancia es al píxel quemado más cercano. |

Lo que Qwen hizo bien: todas las cifras (198, 110, 1 647, 85 %, 100 y 150 m, 3 300–4 100 m) están en el informe, y escribió «mil seiscientas» en femenino.

Las cifras se verifican con código; las afirmaciones las verifica una persona.
