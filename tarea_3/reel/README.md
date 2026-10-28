# Reel: Piura bajo el agua (Parte 3 de la Tarea 3)

Reel vertical de 60 s (1080 × 1920, 30 fps) que cuenta los hallazgos del dashboard
[Piura bajo el agua](https://cris92w.github.io/Python-Intermedio/tarea_3/web/) a un público general. La narración es
mi voz clonada con IA (Qwen3-TTS) a partir de una grabación propia de 17 s.

| Archivo | Qué es |
|---|---|
| `reel.mp4` | El reel final, con narración, música, subtítulos y créditos |
| `reel.srt` | Los subtítulos sincronizados, por separado |
| `portada.png` | La portada para LinkedIn |
| `guion.json` | El guion: lo que se narra (cifras en palabras) y lo que se lee (cifras en dígitos) |
| `voz.py` | Narración con Qwen3-TTS y control de cada escena con Whisper |
| `video.py` | Mapas y gráficos animados, subtítulos, mezcla de audio y codificación |
| `preparar.py` | Descarga el mapa base, las tipografías y la música |
| `capturas.py` | Capturas verticales del dashboard publicado |

## Guion

Seis escenas de una idea cada una. Las cifras salen de `../web/data/resumen.json` y `serie.json`, los mismos datos del
dashboard.

| # | Narración | Qué se ve | De dónde sale cada cifra |
|---|---|---|---|
| 1 | En 2017, el desierto de Sechura se inundó por el fenómeno del Niño. En 2023 volvió a pasar. ¿Cuánta agua fue, y cuánto tiempo se quedó? | Imagen satelital de Piura que se acerca a Sechura mientras aparece el agua del radar de 2017 y luego la de 2023 | Capas `agua_2017.png` y `agua_2023.png` del dashboard (Copernicus GFM) |
| 2 | Lo medí con el radar Sentinel-1, que ve a través de las nubes: 92 pasadas sobre Piura, sin contar el agua de un año normal. | Las pasadas del radar aparecen una a una en una línea de tiempo de diciembre a junio | 43 fechas en 2017 y 49 en 2023 con radar sobre Piura (`serie.json`); 32 km² de agua habitual en 2022 |
| 3 | Resultado: 304 km² de agua anómala en 2017, y 255 en 2023. Casi tres cuartas partes, en Sechura. | Contador sobre el mapa con el agua de cada año; luego Sechura resaltado en dorado | 304,0 y 254,5 km² (`resumen.json`); Sechura: 218,0 de 304,0 km² (72 %) y 187,7 de 254,5 km² (74 %) |
| 4 | En 2023 el agua tardó más en irse: tocó su máximo el 9 de mayo, y a fines de junio aún cubría 165 km². | Curva de 2017 y curva de 2023 que se dibuja en vivo, con el máximo y el último dato marcados | Pasadas que cubren ≥ 90 % de Piura: máximo de 227,6 km² el 9 may 2023; 164,8 km² el 26 jun 2023; en 2017, 43,6 km² el 31 may |
| 5 | Hubo menos daño: los damnificados bajaron de casi 90 000 a menos de 30 000. Pero el radar no ve dentro de las ciudades, ni los huaicos. | Barras de INDECI que crecen; luego el mapa de la sierra con los 455 huaicos de INGEMMET y la ciudad de Piura marcada | INDECI: 89 709 y 29 493 damnificados (−67 %); el radar vio con agua 14 de los 1 322 edificios afectados en 2017 (ciudad de Piura y Bajo Piura) y 0 de 455 huaicos |
| 6 | Explora cada distrito en mi dashboard: Piura bajo el agua. | El dashboard en un celular: portada, mapa narrativo y explorador | Capturas del dashboard publicado |

Narración con imagen: 54,6 s. Al final, unos 5 s de créditos con música; sobre ellos mi voz dice «Los desastres
naturales pasan, los datos quedan.», sin subtítulo ni texto en pantalla (en guion.json, la entrada "despedida" con
"solo_voz").

**Advertencia sobre la escena 5.** Las cifras de INDECI de 2023 cubren enero a junio y todas las emergencias. Las de
2017 cubren enero a mayo y solo el Niño Costero. Por eso la comparación subestima la caída, y el video lo dice en
pantalla.

## Cómo se hizo

1. **Guion.** Redactado a partir de los hallazgos del dashboard. Cada escena tiene dos textos:
   - `frase`, con las cifras en palabras, es lo que dice la voz;
   - `subtitulo`, con dígitos, es lo que se lee en pantalla.
2. **Voz.** `voz.py` clona mi voz con Qwen3-TTS 0.6B a partir de `mi_voz.ogg`, una grabación propia de 17 s que no
   se sube al repositorio.
   - Whisper transcribe cada escena generada. Si entiende mal más del 25 % de las palabras, la escena se genera de
     nuevo; así se revisa que las cifras se pronuncien bien. Las seis escenas quedaron con 0 % de error.
   - Cada toma tiene un tope de largo (0,55 s por palabra más 4 s). Sin tope, el modelo a veces no cierra la frase y
     sigue hasta casi 3 minutos de audio.
   - Al unir las escenas, los silencios internos se acortan a 0,35 s y se quita la cola muda. En la escena 5, el
     modelo había dejado 6,8 s de silencio al final; la narración bajó de 65,3 a 54,6 s sin acelerar la voz.
   - Los tiempos de cada palabra sirven para los subtítulos y para disparar las animaciones.
3. **Imagen.** `video.py` dibuja cada cuadro con Pillow:
   - mapa satelital de Esri en Web Mercator con las capas de agua del dashboard y los límites del INEI;
   - gráficos animados de las pasadas, la curva del agua y las barras de INDECI;
   - mapa de huaicos y capturas del dashboard.

   Los colores y las tipografías (Archivo e IBM Plex Mono) son los del dashboard.
4. **Audio.**
   - La voz se lleva a −14 LUFS, el volumen de redes sociales.
   - La música queda 16 dB por debajo mientras hay narración y sube en los créditos, con fundidos de entrada y salida.
5. **Transparencia.** El aviso «Voz generada con IA» está a la vista todo el video. Cada escena muestra su fuente, y
   los créditos finales nombran datos, imágenes, música y herramienta de voz.

## Reproducirlo

```bash
cd tarea_3/reel
../../PRACTICA_2/.venv/Scripts/python preparar.py   # mapa base, tipografías y música
../.venv/Scripts/python capturas.py                 # capturas del dashboard publicado
../../PRACTICA_2/.venv/Scripts/python voz.py        # narración (requiere mi_voz.ogg y el modelo Qwen3-TTS de PRACTICA_2)
../../PRACTICA_2/.venv/Scripts/python video.py      # reel.mp4, reel.srt y portada.png
```

Se usan dos entornos:
- **El de PRACTICA_2** (qwen-tts, faster-whisper, Pillow, imageio-ffmpeg; ver `../../PRACTICA_2/requirements.txt`) para la voz y el video.
- **El de la tarea** (`websocket-client`) para las capturas.

## Créditos y licencias

- **Voz:** generada con IA (Qwen3-TTS-12Hz-0.6B-Base, Alibaba Qwen) a partir de una grabación de mi propia voz.
- **Datos:**
  - Copernicus Global Flood Monitoring (GFM) sobre Sentinel-1.
  - Copernicus EMS, activación EMSR199.
  - INDECI, compendios estadísticos 2017 y 2023.
  - INGEMMET, inventario de peligros geológicos.
  - INEI, límite distrital 2020.
- **Imagen satelital:** Esri World Imagery (Esri, Maxar, Earthstar Geographics).
- **Música:** «Floating Cities», Kevin MacLeod (incompetech.com). Licencia Creative Commons Attribution 4.0
  (https://creativecommons.org/licenses/by/4.0/).
- **Tipografías:** Archivo e IBM Plex Mono (Google Fonts, SIL Open Font License).
- **Código:** escrito con apoyo de IA (Claude Code), a partir del flujo de la Sesión 15 y de mi Práctica 2.
