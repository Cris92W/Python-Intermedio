# Tarea 3 – ¿Dónde golpeó el agua? El Niño Costero de 2017 y de 2023 visto desde el espacio

**Dashboard:** https://cris92w.github.io/Python-Intermedio/tarea_3/web/
**Publicación de LinkedIn:** (pendiente)

## 1. Tema y pregunta de investigación

Lluvias, inundaciones y huaicos de los Niños Costeros de 2017 y 2023 en la costa norte y centro del Perú.

> ¿Cuánto territorio y cuántas viviendas de Piura, Lambayeque, La Libertad, Áncash y Lima afectaron las lluvias,
> inundaciones y huaicos de los Niños Costeros de 2017 y 2023, y qué detectan —y qué omiten— las imágenes
> satelitales frente a los registros oficiales?

- **Cobertura geográfica:** 5 departamentos, 523 distritos (146 177 km²). Lima es el departamento 15; el Callao queda fuera.
- **Cobertura temporal:** 2017 = diciembre 2016 a mayo 2017; 2023 = enero a junio 2023 (incluye el ciclón Yaku;
  se amplió desde abril porque el agua en Piura seguía creciendo al cierre, y así coincide con los datos de INDECI
  2023). Año de referencia sin Niño: enero a junio 2022.

## 2. Descripción

Se midió la superficie inundada por distrito con radar satelital (Sentinel-1, procesado por Copernicus GFM), se
validó contra la delimitación manual de Copernicus EMS de 2017, se cruzó con los daños oficiales de INDECI y se
ubicaron en 3D los edificios dentro de zonas inundadas o de huaico en Piura y Trujillo.

## 3. Fuentes de datos (consultadas el 26/10/2026)

| Fuente | Qué se usó | Acceso |
|---|---|---|
| Copernicus Global Flood Monitoring (GFM) | 2 093 escenas de inundación (20 m): 718 de 2017, 858 de 2023 y 517 de 2022 | Catálogo STAC abierto de EODC: https://stac.eodc.eu/api/v1 (colección `GFM`) |
| Copernicus EMS, activación EMSR199 | Delimitación de inundación y huaico, y grado de daño por manzana (marzo–abril 2017) | https://mapping.emergency.copernicus.eu/activations/EMSR199/ |
| INDECI, Compendio Estadístico 2017 | Daños del Niño Costero por departamento (pp. 13–15, corte al 04/07/2017) | https://cdn.www.gob.pe/uploads/document/file/1048401/20180227171454120200726-15599-1ptpifw.pdf |
| INDECI, Compendio Estadístico 2023 | Daños del primer semestre 2023 por departamento y por mes (pp. 233–237) | https://cdn.www.gob.pe/uploads/document/file/5591372/4965310-compendio-final-af-2023-indeci.pdf |
| Microsoft Global ML Building Footprints | Huellas de edificios en Piura (126 082) y Trujillo (150 313), licencia ODbL | https://github.com/microsoft/GlobalMLBuildingFootprints |
| INEI, límite distrital 2020 | 1 874 distritos (vía dataset del curso en Hugging Face) | `aquiro1994/ds-python-up`, `_data/LIMITE_DISTRITAL_2020_INEI.zip` |

## 4. Metodología

1. **Inundación con radar.** GFM marca en cada imagen Sentinel-1 el agua que no es habitual para ese mes. Se leyeron
   las escenas directamente del catálogo (archivos COG, vista de 80 m) y se contaron los píxeles inundados por
   distrito. Para no contar dos veces, las escenas de una misma fecha y tile se combinan antes de contar.
2. **Agua habitual.** La máscara de agua habitual de GFM se armó con datos de 2017 a 2021, así que no basta para esta
   costa. Se procesó igual enero–junio de 2022, un año sin Niño. La **inundación anómala** solo cuenta los píxeles con
   agua en al menos dos fechas del evento que en 2022 nunca tuvieron agua.
3. **Corrección de área.** La proyección de GFM (Equi7) agranda las áreas un 2 % en la costa peruana; se corrige.
4. **Validación.** Por cada área mapeada por Copernicus EMS en 2017 se mide qué porcentaje de su inundación también
   detectó el radar.
5. **Edificios.** Un edificio cuenta como afectado si su centro cae en una zona inundada o de huaico de Copernicus,
   en una manzana con daño o en la mancha del radar.
6. **Daños oficiales.** Las cifras de INDECI se transcribieron de los compendios y se verificaron contra la imagen de
   cada tabla.

## 5. Tres hallazgos

1. **El agua se quedó en el desierto del norte, por semanas.** Piura y Lambayeque concentran el 97 % de la inundación
   anómala de 2017 (450 de 464 km²) y el 99 % de la de 2023 (332 de 336 km²). En Piura el máximo de 2017 fue el
   4 de abril (240 km²), una semana después del desborde del río Piura del 27 de marzo, y el de 2023 llegó recién el
   9 de mayo (228 km²), dos meses después del ciclón Yaku.
2. **El radar no ve dónde vive la gente.** Frente a Copernicus EMS 2017, el radar detectó el 46 % de la inundación
   del Bajo Piura, entre 10 y 16 % en Sechura y 0 % en las zonas urbanas y de huaicos de Trujillo y Lima. Copernicus
   ubica 4 908 edificios en zonas afectadas de Piura y Trujillo; el radar, 23.
3. **En 2023 hubo menos agua, y el daño cayó mucho más.** La inundación anómala de 2023 fue el 72 % de la de 2017,
   pero los damnificados bajaron al 38 % (101 120 frente a 267 039) y las viviendas destruidas al 20 % en los cinco
   departamentos.

## 6. Limitaciones

- El radar subestima la inundación urbana (el pulso rebota en las paredes) y no ve los huaicos ni las crecidas de horas.
- Solo ve lo que estaba inundado al pasar (cada 3 a 5 días); cada pasada cubre una parte del territorio.
- Arena seca, salinas y arrozales pueden parecer agua; la referencia de 2022 descuenta lo habitual, pero es un solo
  año, y en enero y febrero de 2022 el radar pasó pocas veces (3 y 5 fechas).
- INDECI 2023 incluye todas las emergencias del primer semestre; el informe de 2017 es específico del Niño Costero.
- Los edificios de Microsoft vienen de imágenes de varios años: en 2017 algunas casas aún no existían. La altura
  en el 3D es ilustrativa.

## 7. Cómo reproducirlo

Requiere Python 3.12 y [uv](https://docs.astral.sh/uv/). Desde `tarea_3/`:

```bash
uv venv .venv --python 3.12
uv pip install --python .venv/Scripts/python.exe -r requirements.txt   # en Linux/Mac: .venv/bin/python

.venv/Scripts/python.exe scripts/obtener_limites.py      # límites INEI de los 5 departamentos
.venv/Scripts/python.exe scripts/inventario_gfm.py       # escenas GFM de 2017, 2023 y 2022
.venv/Scripts/python.exe scripts/procesar_gfm.py         # km² inundados por distrito y fecha (~50 min)
.venv/Scripts/python.exe scripts/obtener_ems_2017.py     # mapas de Copernicus EMS 2017 (~230 MB)
.venv/Scripts/python.exe scripts/obtener_edificios.py    # edificios de Microsoft (Piura y Trujillo)
.venv/Scripts/python.exe scripts/edificios_afectados.py  # clasificación de edificios y capas del 3D
.venv/Scripts/python.exe scripts/validar_gfm_ems.py      # radar frente a Copernicus EMS
.venv/Scripts/python.exe scripts/analizar_datos.py       # indicadores y datos de la web
```

Las descargas van a `datos/originales/` (no se versiona). Los resultados quedan en `datos/procesados/` y
`web/data/`. Para ver el dashboard en local: `python -m http.server -d web 8000` y abrir http://localhost:8000.

## 8. Uso de inteligencia artificial

El análisis, el código y el dashboard se desarrollaron con apoyo de Claude Code. Las cifras se verificaron contra
las fuentes originales: las tablas de INDECI se leyeron sobre la imagen de cada página, y los resultados del radar
se contrastaron con la delimitación manual de Copernicus EMS.
