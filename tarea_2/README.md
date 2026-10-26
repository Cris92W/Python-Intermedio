# Tarea 2 – Voces y documentos peruanos: del archivo escaneado al texto buscable

> ¿Pueden convertir documentos escaneados y entrevistas en audio en un archivo de texto
> estructurado y buscable?

## Corpus

Los archivos se bajaron con `descargar_datos.py`: el audio el 22 de octubre de 2026 y los documentos
el 23 de octubre de 2026. El detalle de cada archivo está en [`datos/fuentes.csv`](datos/fuentes.csv):
fuente, licencia, autor, descripción, forma de acceso y si se usó o se descartó.

### A. Documentos (25 + 1 suplente)

Todos vienen de Wikimedia Commons.

| Tipo | Documentos | Qué son | Licencias |
|---|---|---|---|
| Impreso nítido | 8 | Proclama virreinal (1808), folletos de Lima (1804 y década de 1820), Constitución de 1860, drama en verso (1861), *Tradiciones peruanas*, *Colección de los tratados del Perú* y revista *Variedades* (1909) | Dominio público |
| Foto con sombra o inclinación | 8 | Placas y letreros fotografiados en ángulo, con relieve o con sombras (Lima, Cusco y Machu Picchu) | CC BY-SA 3.0 / 4.0, CC0 |
| Manuscrito | 9 | Pizarras de menú escritas con plumón o tiza, letreros rotulados a mano y carteles escritos a mano en una marcha (Lima, Cusco, Áncash, Junín; 2010-2024) | CC BY-SA 3.0 / 4.0, CC BY 2.0, dominio público |

Se bajaron 26 documentos. `doc_022` se descartó porque el OCR solo leyó 7 caracteres, y lo
reemplaza el suplente `doc_026`, del mismo tipo.

En las fotos de pizarras y carteles se guardó solo la zona escrita. Lo que quedaba fuera del cartel,
como los rostros de quienes marchaban, se difuminó.

### B. Audio (29 clips, 44,1 minutos)

| Fuente | Clips | Minutos | Licencia |
|---|---|---|---|
| Wikimedia Commons: entrevistas en español peruano (Lima, Áncash, sierra central, San Martín) | 17 | 36,2 | CC BY-SA 4.0 / CC BY 4.0 |
| archive.org: entrevistas de Radio Bomba (Lima) | 2 | 6,9 | CC BY-NC-SA 3.0 / 4.0 |
| OpenSLR 73: frases leídas en español peruano (Google) | 10 | 1,0 | CC BY-SA 4.0 |

Varios clips tienen dos o más hablantes. Por ejemplo, `clip_002` es una entrevista callejera con
tres voces y `clip_011` reúne entrevistas en una marcha.

### Fuente y licencia de cada archivo

<details>
<summary>Ver los 55 archivos (26 documentos y 29 clips)</summary>

| id | Tipo | Descripción | Fuente | Licencia | Estado |
|---|---|---|---|---|---|
| `doc_001` | impreso | Proclama del virrey del Perú a sus habitantes (Lima, 1808), página 2 | [Wikimedia Commons](https://commons.wikimedia.org/?curid=151264038) | Dominio público | usado |
| `doc_002` | impreso | Folleto «Cartas históricas a un amigo» (Lima, 1804), página en tipografía cursiva | [Wikimedia Commons](https://commons.wikimedia.org/?curid=92578328) | Dominio público | usado |
| `doc_003` | impreso | Folleto «Exposición que hace un peruano al virrey La Serna» (1821-1824), página 2 del texto | [Wikimedia Commons](https://commons.wikimedia.org/?curid=195271495) | Dominio público | usado |
| `doc_004` | impreso | Constitución Política del Perú reformada por el Congreso de 1860 (Lima, Imprenta de José María Masías), inicio del texto | [Wikimedia Commons](https://commons.wikimedia.org/?curid=147422002) | Dominio público | usado |
| `doc_005` | impreso | Drama en verso «El amor y el oro» (Lima, 1861), acto I, escena X | [Wikimedia Commons](https://commons.wikimedia.org/?curid=157158887) | Dominio público | usado |
| `doc_006` | impreso | Libro «Tradiciones peruanas», tomo I (c. 1893), página 33 | [Wikimedia Commons](https://commons.wikimedia.org/?curid=197917146) | Dominio público | usado |
| `doc_007` | impreso | Colección de los tratados del Perú, tomo V (Lima, c. 1890-1911), página 34 | [Wikimedia Commons](https://commons.wikimedia.org/?curid=94970165) | Dominio público | usado |
| `doc_008` | impreso | Revista «Variedades» n.º 62 (Lima, 8 de mayo de 1909), página 237: notas «El globo Inca» y «El callejón de Otaiza» | [Wikimedia Commons](https://commons.wikimedia.org/?curid=196375232) | Dominio público | usado |
| `doc_009` | foto | Foto en perspectiva de una placa de mármol en la Catedral de Lima por la segunda visita papal (1988) | [Wikimedia Commons](https://commons.wikimedia.org/?curid=9538716) | CC BY-SA 3.0 | usado |
| `doc_010` | foto | Foto inclinada de la placa de inauguración de los mercados Minorista y Mayorista de La Parada (Lima, 1945) | [Wikimedia Commons](https://commons.wikimedia.org/?curid=173479651) | CC0 | usado |
| `doc_011` | foto | Foto en ángulo de una placa de bronce en relieve en la antigua casa de un alcalde de Lima (Jr. Huallaga) | [Wikimedia Commons](https://commons.wikimedia.org/?curid=151281616) | CC BY-SA 4.0 | usado |
| `doc_012` | foto | Foto de una placa de bronce oscuro a un poeta del virreinato, autor de «La Cristiada» (Pasaje Acisclo Villarán, Lima) | [Wikimedia Commons](https://commons.wikimedia.org/?curid=167747930) | CC BY-SA 4.0 | usado |
| `doc_013` | foto | Foto de un letrero de letras metálicas con sombra sobre muro de piedra (Paraninfo Universitario, Cusco) | [Wikimedia Commons](https://commons.wikimedia.org/?curid=118043633) | CC BY-SA 4.0 | usado |
| `doc_014` | foto | Foto inclinada del letrero del Antiguo Hospital de los Bethlemitas sobre muro desgastado (Cusco) | [Wikimedia Commons](https://commons.wikimedia.org/?curid=138329505) | CC BY-SA 4.0 | usado |
| `doc_015` | foto | Foto al aire libre, en ángulo, del cartel del Ministerio de Cultura del Arco de Picchu (Cusco) | [Wikimedia Commons](https://commons.wikimedia.org/?curid=85757339) | CC BY-SA 4.0 | usado |
| `doc_016` | foto | Foto de la placa de inauguración de la estación ferroviaria Aguas Calientes-Machupicchu (1998) | [Wikimedia Commons](https://commons.wikimedia.org/?curid=98194645) | CC BY-SA 4.0 | usado |
| `doc_017` | manuscrito | Menú del día escrito con plumón en una pizarra blanca (restaurante de San Marcos, Áncash, 2010) | [Wikimedia Commons](https://commons.wikimedia.org/?curid=10214342) | CC BY-SA 4.0 | usado |
| `doc_018` | manuscrito | Menú escrito con tiza en una pizarra de un restaurante de Lima (2012) | [Wikimedia Commons](https://commons.wikimedia.org/?curid=79662461) | CC BY 2.0 | usado |
| `doc_019` | manuscrito | Pizarra de un restaurante de Miraflores con sugerencias y menú del día escritos con tiza de colores (2017) | [Wikimedia Commons](https://commons.wikimedia.org/?curid=58342463) | CC BY-SA 4.0 | usado |
| `doc_020` | manuscrito | Pizarra rotulada a mano de una cevichería del Mercado de Cusco (2011) | [Wikimedia Commons](https://commons.wikimedia.org/?curid=15585870) | CC BY-SA 3.0 | usado |
| `doc_021` | manuscrito | Cartel escrito a mano «No hace falta ser la causa para defender la causa» (Marcha del Orgullo, Lima, 2024) | [Wikimedia Commons](https://commons.wikimedia.org/?curid=150112102) | CC BY-SA 4.0 | usado |
| `doc_022` | manuscrito | Cartel de cartón escrito a mano «Mi mamá me enseñó a comer de todo» (Marcha del Orgullo, Lima, 2024) | [Wikimedia Commons](https://commons.wikimedia.org/?curid=150112091) | CC BY-SA 4.0 | descartado: documento ilegible para el OCR |
| `doc_023` | manuscrito | Cartel escrito a mano «Si tu familia no acepta tu orientación sexual…» (Marcha del Orgullo, Lima, 2024) | [Wikimedia Commons](https://commons.wikimedia.org/?curid=150112094) | CC BY-SA 4.0 | usado |
| `doc_024` | manuscrito | Cartel escrito a mano «No pasaremos el resto de nuestros días…» (Marcha del Orgullo, Lima, 2024) | [Wikimedia Commons](https://commons.wikimedia.org/?curid=149907689) | CC BY-SA 4.0 | usado |
| `doc_025` | manuscrito | Letrero pintado a mano con la carta de un recreo campestre (Ingenio, Junín) | [Wikimedia Commons](https://commons.wikimedia.org/?curid=5328569) | Dominio público | usado |
| `doc_026` | manuscrito | Cartel escrito a mano «Mi amor por ti es incondicional» (Marcha del Orgullo, Lima, 2024); reemplaza a doc_022 | [Wikimedia Commons](https://commons.wikimedia.org/?curid=150112107) | CC BY-SA 4.0 | usado |
| `clip_001` | entrevista | Entrevista callejera a una vendedora de frutas (El Agustino, Lima, 2022) | [Wikimedia Commons](https://commons.wikimedia.org/?curid=119251161) | CC BY-SA 4.0 | usado |
| `clip_002` | entrevista | Entrevista callejera a dos vendedoras de dulces (El Agustino, Lima, 2022); tres voces | [Wikimedia Commons](https://commons.wikimedia.org/?curid=119251160) | CC BY-SA 4.0 | usado |
| `clip_003` | entrevista | Entrevista a una dirigente de mujeres indígenas de la sierra central en conferencia de prensa (2022) | [Wikimedia Commons](https://commons.wikimedia.org/?curid=121219890) | CC BY-SA 4.0 | usado |
| `clip_004` | entrevista | Entrevista a una dirigente de base de Apurímac durante una protesta (2022) | [Wikimedia Commons](https://commons.wikimedia.org/?curid=121219891) | CC BY-SA 4.0 | usado |
| `clip_005` | entrevista | Entrevista registrada por un estudiante de la UNMSM (parte 1) | [Wikimedia Commons](https://commons.wikimedia.org/?curid=121363454) | CC BY-SA 4.0 | usado |
| `clip_006` | entrevista | Entrevista registrada por un estudiante de la UNMSM (parte 2) | [Wikimedia Commons](https://commons.wikimedia.org/?curid=121363453) | CC BY-SA 4.0 | usado |
| `clip_007` | entrevista | Entrevista registrada por un estudiante de la UNMSM (parte 3) | [Wikimedia Commons](https://commons.wikimedia.org/?curid=121363455) | CC BY-SA 4.0 | usado |
| `clip_008` | entrevista | Entrevista registrada por un estudiante de la UNMSM (parte 4) | [Wikimedia Commons](https://commons.wikimedia.org/?curid=121363456) | CC BY-SA 4.0 | usado |
| `clip_009` | entrevista | Mini entrevistas en el medio tiempo del repechaje Perú-Australia (2022) | [Wikimedia Commons](https://commons.wikimedia.org/?curid=119262664) | CC BY-SA 4.0 | usado |
| `clip_010` | entrevista | Entrevista durante una marcha (registro de un estudiante de la UNMSM) | [Wikimedia Commons](https://commons.wikimedia.org/?curid=133964620) | CC BY-SA 4.0 | usado |
| `clip_011` | entrevista | Entrevistas durante una marcha, varias voces (registro de un estudiante de la UNMSM) | [Wikimedia Commons](https://commons.wikimedia.org/?curid=133964621) | CC BY-SA 4.0 | usado |
| `clip_012` | entrevista | Entrevista a una señora de Shuyas (Áncash) sobre la fiesta de la Santísima Trinidad | [Wikimedia Commons](https://commons.wikimedia.org/?curid=149433723) | CC BY-SA 4.0 | descartado: audio sin voz |
| `clip_013` | entrevista | Entrevista a una señora de Pomabamba (Áncash) sobre la fiesta de la Santísima Trinidad | [Wikimedia Commons](https://commons.wikimedia.org/?curid=149433722) | CC BY-SA 4.0 | usado |
| `clip_014` | entrevista | Entrevista a una joven participante de una marcha | [Wikimedia Commons](https://commons.wikimedia.org/?curid=119950449) | CC BY-SA 4.0 | usado |
| `clip_015` | entrevista | Entrevista a una organizadora de la fiesta patronal de Tayta Palli de Chuyas | [Wikimedia Commons](https://commons.wikimedia.org/?curid=149445104) | CC BY-SA 4.0 | usado |
| `clip_016` | entrevista | Testimonio de una pobladora del departamento de San Martín (parte 1) | [Wikimedia Commons](https://commons.wikimedia.org/?curid=149666949) | CC BY 4.0 | usado |
| `clip_017` | entrevista | Testimonio de una pobladora del departamento de San Martín (parte 2) | [Wikimedia Commons](https://commons.wikimedia.org/?curid=149666950) | CC BY 4.0 | usado |
| `clip_018` | entrevista | Entrevista en un plantón de familias de Pasco en Lima (Radio Bomba, 2017); ruido de calle | [archive.org (Radio Bomba)](https://archive.org/details/pascoenlima2017) | CC BY-NC-SA 3.0 | usado |
| `clip_019` | entrevista | Entrevista a un dirigente awajún sobre la audiencia del caso Estación 6 (Radio Bomba, 2018) | [archive.org (Radio Bomba)](https://archive.org/details/e6ejsht) | CC BY-NC-SA 4.0 | usado |
| `clip_020` | frase leída | Frase leída en español peruano, hablante anónimo (mujer) | [OpenSLR 73](https://www.openslr.org/73/) | CC BY-SA 4.0 | usado |
| `clip_021` | frase leída | Frase leída en español peruano, hablante anónimo (mujer) | [OpenSLR 73](https://www.openslr.org/73/) | CC BY-SA 4.0 | usado |
| `clip_022` | frase leída | Frase leída en español peruano, hablante anónimo (mujer) | [OpenSLR 73](https://www.openslr.org/73/) | CC BY-SA 4.0 | usado |
| `clip_023` | frase leída | Frase leída en español peruano, hablante anónimo (mujer) | [OpenSLR 73](https://www.openslr.org/73/) | CC BY-SA 4.0 | usado |
| `clip_024` | frase leída | Frase leída en español peruano, hablante anónimo (mujer) | [OpenSLR 73](https://www.openslr.org/73/) | CC BY-SA 4.0 | usado |
| `clip_025` | frase leída | Frase leída en español peruano, hablante anónimo (hombre) | [OpenSLR 73](https://www.openslr.org/73/) | CC BY-SA 4.0 | usado |
| `clip_026` | frase leída | Frase leída en español peruano, hablante anónimo (hombre) | [OpenSLR 73](https://www.openslr.org/73/) | CC BY-SA 4.0 | usado |
| `clip_027` | frase leída | Frase leída en español peruano, hablante anónimo (hombre) | [OpenSLR 73](https://www.openslr.org/73/) | CC BY-SA 4.0 | usado |
| `clip_028` | frase leída | Frase leída en español peruano, hablante anónimo (hombre) | [OpenSLR 73](https://www.openslr.org/73/) | CC BY-SA 4.0 | usado |
| `clip_029` | frase leída | Frase leída en español peruano, hablante anónimo (hombre) | [OpenSLR 73](https://www.openslr.org/73/) | CC BY-SA 4.0 | usado |

</details>

### Licencias

Todos los archivos están en dominio público o tienen licencia Creative Commons. Las licencias
CC BY-NC-SA de Radio Bomba permiten este uso académico, que no es comercial. La atribución que
exigen las licencias CC BY (autor, licencia y enlace) está en `datos/fuentes.csv`.

### Privacidad

- Los archivos locales usan ids neutros (`doc_001`, `clip_001`). Los títulos de Commons suelen
  incluir el nombre de la persona entrevistada, así que se enlazan por su id de página
  (`https://commons.wikimedia.org/?curid=N`) y las descripciones no nombran a nadie.
- Se sigue al pie de la letra la regla «ningún nombre, DNI ni dato personal real puede publicarse».
  En los textos de OCR y en las transcripciones se cambia por `[PERSONA_NN]` el nombre de toda
  persona real, privada o pública. Se mantienen los personajes de ficción y los nombres de lugares
  u organizaciones.
- Los únicos nombres reales que se publican son los autores de la columna `autor` de
  `datos/fuentes.csv`, porque las licencias exigen esa atribución.

## Parte 1: extracción (`01_extraccion.ipynb`)

| Paso | Resultado |
|---|---|
| Configuración | La primera celda registra las fechas de extracción, la fuente y la licencia de cada archivo, y las versiones de PaddleOCR, faster-whisper y el resto de componentes |
| OCR | PaddleOCR 3.7 (PP-OCRv6, `lang=es`) sobre los 26 documentos, en 24 min de CPU. Confianza mediana: 0,99 en impresos, 0,985 en fotos y 0,93 en manuscritos. Se guardan el JSON crudo, las cajas dibujadas y el recorte de cada línea en `datos/raw/documentos/` |
| ASR | faster-whisper `small` (CPU int8, VAD Silero) con diarización por huellas de voz (`voz.py`, Sesión 13). Los 44 min se transcribieron en 21 min, y 14 de los clips válidos tienen 2 o más hablantes. Se exporta a CSV, SRT y TXT |
| Seudonimización | Patrones (DNI, teléfono, correo, dirección), spaCy y revisión humana: 67 menciones de 38 personas pasan a `[PERSONA_NN]` |
| Limpieza | No hay duplicados por hash. Se descartan `doc_022` (el OCR leyó menos de 20 caracteres) y `clip_012` (casi sin voz). `doc_026` reemplaza a `doc_022`. Quedan 25 documentos (8 impresos, 8 fotos, 9 manuscritos) y 28 clips (42,4 min) |
| EDA | 3 gráficos de Plotly Express con títulos analíticos: documentos por tipo, duración por clip y longitud de los textos |
| Validación | Los 3 textos OCR más largos y más cortos y los 3 clips más largos y más cortos, contrastados con los histogramas |
| Salidas | `datos/documentos.csv` (25 filas), `datos/transcripciones.csv` (28) y `datos/fuentes.csv` (55, con la columna `estado`) |

**Hallazgos de la Parte 1**
- La confianza del OCR no garantiza que el texto sea correcto. El clasificador de orientación de
  PaddleOCR giró 180° cuatro fotos. En dos placas devolvió letras sueltas, y el cartel descartado
  tenía confianza de 0,99 con solo dos palabras.
- La diarización sobreestima el número de voces en la calle: detecta 8 en `clip_011` y 7 en
  `clip_014`.

El diccionario de seudónimos (`datos/raw/seudonimos.json`) y las salidas sin seudonimizar
(`datos/raw/audio/salidas/`, `datos/raw/documentos/ocr/`) contienen nombres reales, así que quedan
fuera de Git.

Para ejecutar el notebook se usa el entorno de los grupos `docai` y `audio` del curso. Las versiones
exactas están en `requirements-notebooks.txt`:

```bash
uv venv .venv --python 3.12
uv pip install -p .venv -r requirements-notebooks.txt
.venv/Scripts/jupyter nbconvert --to notebook --execute --inplace 01_extraccion.ipynb
```

### Cómo recuperar los datos

El corpus crudo (unos 300 MB) vive en `datos/raw/` y no se versiona. Para volver a bajarlo:

```bash
cd tarea_2
uv run --no-project --python 3.12 --with requests --with pillow --with pymupdf --with imageio-ffmpeg python descargar_datos.py
```

El script hace lo siguiente:
- Usa un User-Agent descriptivo y espera 1,5 s entre solicitudes.
- Guarda las imágenes en `datos/raw/documentos/` y los originales (fotos y PDF completos) en
  `datos/raw/documentos/originales/`.
- Guarda los audios originales en `datos/raw/audio/originales/` y una copia WAV mono de 16 kHz por
  clip en `datos/raw/audio/`.
- De OpenSLR 73 solo lee del zip las frases elegidas, con peticiones HTTP Range.

## Parte 2: evaluación y extracción estructurada (`02_evaluacion.ipynb`)

La muestra, los cuatro modelos con sus parámetros, el prompt del LLM y los criterios de auditoría se
fijaron el 24 de octubre de 2026. La normalización se fijó el 25 de octubre. Todo quedó fijo antes de
calcular cualquier métrica y está en
[`modelos/configuracion_evaluacion.json`](modelos/configuracion_evaluacion.json).

| Paso | Resultado |
|---|---|
| 1. Muestra | 10 documentos (3 impresos, 3 fotos y 4 manuscritos) y 10 clips (6 entrevistas de Commons y 4 frases de OpenSLR 73, 6,8 min), sorteados por estrato con semilla 2026. Se transcribieron a mano y se seudonimizaron en la columna `texto_referencia` |
| 2. Línea base | PaddleOCR y faster-whisper `small` en CPU, con la configuración de la Parte 1. Referencias y salidas pasan por la misma normalización, sin las marcas `[HABLANTE_N]` |
| 3. LLM | Qwen3-0.6B local (CPU, decodificación voraz) extrae campos JSON de los 53 textos: [`datos/extraccion_llm.csv`](datos/extraccion_llm.csv), con 52 JSON válidos. La auditoría humana de 20 extracciones al azar está en [`datos/auditoria_llm.csv`](datos/auditoria_llm.csv) |
| 4. Comparación | EasyOCR 1.7 ([`ocr_easyocr.py`](ocr_easyocr.py)) y Qwen3-ASR 0.6B, sobre los mismos 20 archivos. Resultados por archivo en [`datos/evaluacion_modelos.csv`](datos/evaluacion_modelos.csv) |
| 5. Casos difíciles | CER por tipo de documento, y WER según la relación señal-ruido de cada clip, estimada con el VAD |
| 6. Decisión | Tabla comparativa con precisión, latencia, tamaño y costo, y elección para un entorno real |

| Modelo | Métrica | Global | Impreso / estudio | Foto | Manuscrito / calle | Latencia en esta CPU | Disco |
|---|---|---|---|---|---|---|---|
| **PaddleOCR** (base) | CER | **0,027** | 0,002 | 0,146 | 0,182 | 56 s por documento | 146 MB |
| EasyOCR | CER | 0,089 | 0,037 | 0,279 | 0,453 | 23 s por documento | 94 MB |
| **faster-whisper `small`** (base) | WER | **0,049** | 0,068 | | 0,048 | factor de tiempo real 0,57 | 464 MB |
| Qwen3-ASR 0.6B | WER | 0,210 | 0,114 | | 0,215 | factor de tiempo real 1,04 | 1 503 MB |

```
Resultados Test: WER: 0.05 | CER: 0.03 | Acuerdo LLM-Humano: 1/20
```

**Hallazgos de la Parte 2**
- **Los modelos base ganan en las dos modalidades.**
  - PaddleOCR comete 3,3 veces menos errores que EasyOCR. Solo pierde en una foto, donde lee los
    renglones de abajo arriba.
  - faster-whisper comete 4,3 veces menos errores que Qwen3-ASR y es casi el doble de rápido.
  - Por eso se eligen los dos modelos base para un entorno real sin GPU.
- **El tipo de documento pesa más que el modelo.** Los impresos salen casi perfectos. En las fotos y
  los manuscritos el CER sube a 0,15–0,18, y ningún modelo lee la pancarta en letra cursiva.
- **Qwen3-ASR se degrada con el ruido.** Sus tres peores clips son las entrevistas con menos de 6 dB de
  relación señal-ruido y varias voces.
- **El LLM pequeño no es confiable sin revisión.** Solo 1 de 20 extracciones está completamente correcta,
  aunque el 69 % de los campos está bien.
  - Copia el ejemplo del prompt («S/ 15.00») como monto en 8 documentos.
  - Otros errores vienen de la entrada: la regla del prompt para el número de hablantes, la
    seudonimización de figuras públicas y un OCR ilegible.

**Limitaciones**
- La muestra es pequeña: 10 archivos por modalidad. En las 4 frases de estudio (44 palabras), cada error
  pesa 2,3 puntos de WER.
- Una sola persona hizo la auditoría, y en varios campos juzgó contra el archivo original en lugar del
  texto que recibió el LLM.
- La normalización no convierte cifras en palabras, así que «la 1» cuenta como error frente a «la una».

**Privacidad.** Las referencias manuales, las salidas de EasyOCR y Qwen3-ASR, las extracciones del LLM y
los comentarios de la auditoría se seudonimizan con el mismo diccionario de la Parte 1. spaCy busca
después los nombres que quedan, y cada candidato se revisa a mano en el notebook. Las transcripciones
manuales sin seudonimizar (`datos/raw/muestra_evaluacion/`) y la planilla de auditoría
(`datos/raw/auditoria_llm/`) quedan fuera de Git.

**Ejecución.** Usa el mismo `.venv` de la Parte 1:

```bash
.venv/Scripts/jupyter nbconvert --to notebook --execute --inplace 02_evaluacion.ipynb
```

- El notebook lee las salidas guardadas en `datos/raw/`. Si no existen, vuelve a correr cada modelo.
- EasyOCR corre en un entorno aparte, porque su OpenCV choca con el de PaddleOCR:
  `uv run --no-project --python 3.12 --with easyocr==1.7.2 --with pandas python ocr_easyocr.py`.

**Uso de IA.** El trabajo se hizo con Claude Code. Las capturas de la conversación están en
[`evidencias_ia/`](evidencias_ia/), numeradas en orden.
