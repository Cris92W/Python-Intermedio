"""Descarga el corpus de la Tarea 2 y registra fuente, licencia y autor de cada archivo.

    uv run --no-project --python 3.12 --with requests --with pillow --with pymupdf --with imageio-ffmpeg python descargar_datos.py

Qué baja (unos 300 MB, todo a datos/raw/, que no se versiona):

- Corpus A, documentos (25): 8 impresos nítidos, 8 fotos con sombra o inclinación y 9 manuscritos,
  todos de Wikimedia Commons. Se guardan como datos/raw/documentos/doc_XXX.jpg (lado mayor de 3000 px
  como máximo); el archivo original (foto o PDF completo) queda en datos/raw/documentos/originales/.
  De los PDF se renderiza la página elegida. En las fotos de pizarras y carteles se recorta la zona
  escrita y se difumina lo que queda fuera del cartel (rostros de personas en marchas).
- Corpus B, audio (29 clips, ~44 min): entrevistas en español peruano de Wikimedia Commons,
  entrevistas de Radio Bomba en archive.org y frases leídas de OpenSLR 73 (español peruano).
  Se guarda el archivo original en datos/raw/audio/originales/ y una copia WAV mono de 16 kHz
  en datos/raw/audio/clip_XXX.wav (la frecuencia que esperan los modelos de voz).

Al final escribe datos/fuentes.csv (id, modalidad, fuente_url, licencia, acceso y la atribución).

Privacidad: los títulos de muchos archivos de Commons llevan el nombre de la persona entrevistada.
Por eso aquí se identifican por su pageid y la URL publicada es https://commons.wikimedia.org/?curid=N,
que lleva a la misma página sin escribir el nombre. Los archivos locales usan ids neutros.

Buenas prácticas: User-Agent descriptivo, pausa de 1,5 s entre solicitudes y reintentos ante 429/5xx.
La lectura parcial de los zip de OpenSLR (HTTP Range) sigue la idea de datos.py de la Sesión 13.
"""
import csv
import io
import random
import re
import subprocess
import time
import wave
import zipfile
from datetime import date
from pathlib import Path

import imageio_ffmpeg
import pymupdf
import requests
from PIL import Image, ImageDraw, ImageFilter, ImageOps

Image.MAX_IMAGE_PIXELS = None
BASE = Path(__file__).resolve().parent
RAW_DOC = BASE / "datos" / "raw" / "documentos"
RAW_AUD = BASE / "datos" / "raw" / "audio"
FUENTES = BASE / "datos" / "fuentes.csv"

# Wikimedia exige un User-Agent con contacto en forma de URL; sin él responde 429 a las descargas.
UA = {"User-Agent": f"tarea2-ds-python/2026 (https://github.com/Cris92W; tarea académica) python-requests/{requests.__version__}"}
PAUSA = 1.5
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
OPENSLR73 = "https://www.openslr.org/resources/73/es_pe_{sexo}.zip"
SR = 16_000
LADO_MAX = 3000

# ---------------------------------------------------------------------------------------------
# Corpus A: documentos de Wikimedia Commons. (id, tipo, pageid, página, descripción)
#   página solo para PDF/DjVu: se usa esa página del archivo.
# Las descripciones no nombran a personas: el texto publicado no lleva nombres reales.
# Suplentes revisados por si algún documento resulta ilegible en el OCR (el notebook descarta los
# que dan menos de 20 caracteres o confianza menor que 0,40, y hay que reemplazarlos):
#   impresos:    pageid 184620635 (Almanaque de El Cascabel para 1873, página 8)
#   manuscritos: pageid 150112107 -> ya en uso como doc_026, que reemplaza a doc_022 (el OCR solo leyó
#                «DE TODO»: giró la foto 180°); siguiente suplente: pageid 5328598 (otro letrero del
#                mismo recreo de Ingenio, Junín)
# ---------------------------------------------------------------------------------------------
DOCUMENTOS = [
    ("doc_001", "impreso", 151264038, 2, "Proclama del virrey del Perú a sus habitantes (Lima, 1808), página 2"),
    ("doc_002", "impreso", 92578328, 9, "Folleto «Cartas históricas a un amigo» (Lima, 1804), página en tipografía cursiva"),
    ("doc_003", "impreso", 195271495, 8, "Folleto «Exposición que hace un peruano al virrey La Serna» (1821-1824), página 2 del texto"),
    ("doc_004", "impreso", 147422002, 5, "Constitución Política del Perú reformada por el Congreso de 1860 (Lima, Imprenta de José María Masías), inicio del texto"),
    ("doc_005", "impreso", 157158887, 20, "Drama en verso «El amor y el oro» (Lima, 1861), acto I, escena X"),
    ("doc_006", "impreso", 197917146, 40, "Libro «Tradiciones peruanas», tomo I (c. 1893), página 33"),
    ("doc_007", "impreso", 94970165, 40, "Colección de los tratados del Perú, tomo V (Lima, c. 1890-1911), página 34"),
    ("doc_008", "impreso", 196375232, 9, "Revista «Variedades» n.º 62 (Lima, 8 de mayo de 1909), página 237: notas «El globo Inca» y «El callejón de Otaiza»"),
    ("doc_009", "foto", 9538716, None, "Foto en perspectiva de una placa de mármol en la Catedral de Lima por la segunda visita papal (1988)"),
    ("doc_010", "foto", 173479651, None, "Foto inclinada de la placa de inauguración de los mercados Minorista y Mayorista de La Parada (Lima, 1945)"),
    ("doc_011", "foto", 151281616, None, "Foto en ángulo de una placa de bronce en relieve en la antigua casa de un alcalde de Lima (Jr. Huallaga)"),
    ("doc_012", "foto", 167747930, None, "Foto de una placa de bronce oscuro a un poeta del virreinato, autor de «La Cristiada» (Pasaje Acisclo Villarán, Lima)"),
    ("doc_013", "foto", 118043633, None, "Foto de un letrero de letras metálicas con sombra sobre muro de piedra (Paraninfo Universitario, Cusco)"),
    ("doc_014", "foto", 138329505, None, "Foto inclinada del letrero del Antiguo Hospital de los Bethlemitas sobre muro desgastado (Cusco)"),
    ("doc_015", "foto", 85757339, None, "Foto al aire libre, en ángulo, del cartel del Ministerio de Cultura del Arco de Picchu (Cusco)"),
    ("doc_016", "foto", 98194645, None, "Foto de la placa de inauguración de la estación ferroviaria Aguas Calientes-Machupicchu (1998)"),
    ("doc_017", "manuscrito", 10214342, None, "Menú del día escrito con plumón en una pizarra blanca (restaurante de San Marcos, Áncash, 2010)"),
    ("doc_018", "manuscrito", 79662461, None, "Menú escrito con tiza en una pizarra de un restaurante de Lima (2012)"),
    ("doc_019", "manuscrito", 58342463, None, "Pizarra de un restaurante de Miraflores con sugerencias y menú del día escritos con tiza de colores (2017)"),
    ("doc_020", "manuscrito", 15585870, None, "Pizarra rotulada a mano de una cevichería del Mercado de Cusco (2011)"),
    ("doc_021", "manuscrito", 150112102, None, "Cartel escrito a mano «No hace falta ser la causa para defender la causa» (Marcha del Orgullo, Lima, 2024)"),
    ("doc_022", "manuscrito", 150112091, None, "Cartel de cartón escrito a mano «Mi mamá me enseñó a comer de todo» (Marcha del Orgullo, Lima, 2024)"),
    ("doc_023", "manuscrito", 150112094, None, "Cartel escrito a mano «Si tu familia no acepta tu orientación sexual…» (Marcha del Orgullo, Lima, 2024)"),
    ("doc_024", "manuscrito", 149907689, None, "Cartel escrito a mano «No pasaremos el resto de nuestros días…» (Marcha del Orgullo, Lima, 2024)"),
    ("doc_025", "manuscrito", 5328569, None, "Letrero pintado a mano con la carta de un recreo campestre (Ingenio, Junín)"),
    ("doc_026", "manuscrito", 150112107, None, "Cartel escrito a mano «Mi amor por ti es incondicional» (Marcha del Orgullo, Lima, 2024); reemplaza a doc_022"),
]

# Recorte relativo (izquierda, arriba, derecha, abajo) para quedarse con la zona escrita.
RECORTES = {
    "doc_017": (0.065, 0.225, 0.81, 0.86),
    "doc_018": (0.20, 0.11, 0.82, 0.96),
    "doc_019": (0.085, 0.225, 0.91, 0.775),
    "doc_020": (0.33, 0.015, 0.655, 0.995),
    "doc_021": (0.245, 0.48, 0.52, 0.69),
    "doc_022": (0.28, 0.42, 0.68, 0.80),
    "doc_023": (0.255, 0.435, 0.61, 0.645),
    "doc_024": (0.185, 0.205, 0.44, 0.395),
    "doc_026": (0.22, 0.28, 0.80, 0.615),
}
# Borde del cartel en la foto completa (coordenadas relativas): lo de afuera se difumina antes del
# recorte, para que no quede ningún rostro reconocible.
CARTELES = {
    "doc_018": [(0.21, 0.125), (0.745, 0.115), (0.805, 0.93), (0.245, 0.955)],
    "doc_021": [(0.255, 0.505), (0.505, 0.487), (0.512, 0.665), (0.262, 0.682)],
    "doc_022": [(0.298, 0.523), (0.445, 0.432), (0.668, 0.675), (0.505, 0.79)],
    "doc_026": [(0.235, 0.29), (0.79, 0.325), (0.77, 0.61), (0.25, 0.605)],
}

# ---------------------------------------------------------------------------------------------
# Corpus B: audio. (id, repositorio, referencia, descripción)
#   commons -> pageid; archive -> identificador (se baja el MP3 original del ítem)
# Los clips de OpenSLR 73 (clip_020 en adelante) se eligen al azar con semilla fija.
# ---------------------------------------------------------------------------------------------
AUDIOS = [
    ("clip_001", "commons", 119251161, "Entrevista callejera a una vendedora de frutas (El Agustino, Lima, 2022)"),
    ("clip_002", "commons", 119251160, "Entrevista callejera a dos vendedoras de dulces (El Agustino, Lima, 2022); tres voces"),
    ("clip_003", "commons", 121219890, "Entrevista a una dirigente de mujeres indígenas de la sierra central en conferencia de prensa (2022)"),
    ("clip_004", "commons", 121219891, "Entrevista a una dirigente de base de Apurímac durante una protesta (2022)"),
    ("clip_005", "commons", 121363454, "Entrevista registrada por un estudiante de la UNMSM (parte 1)"),
    ("clip_006", "commons", 121363453, "Entrevista registrada por un estudiante de la UNMSM (parte 2)"),
    ("clip_007", "commons", 121363455, "Entrevista registrada por un estudiante de la UNMSM (parte 3)"),
    ("clip_008", "commons", 121363456, "Entrevista registrada por un estudiante de la UNMSM (parte 4)"),
    ("clip_009", "commons", 119262664, "Mini entrevistas en el medio tiempo del repechaje Perú-Australia (2022)"),
    ("clip_010", "commons", 133964620, "Entrevista durante una marcha (registro de un estudiante de la UNMSM)"),
    ("clip_011", "commons", 133964621, "Entrevistas durante una marcha, varias voces (registro de un estudiante de la UNMSM)"),
    ("clip_012", "commons", 149433723, "Entrevista a una señora de Shuyas (Áncash) sobre la fiesta de la Santísima Trinidad"),
    ("clip_013", "commons", 149433722, "Entrevista a una señora de Pomabamba (Áncash) sobre la fiesta de la Santísima Trinidad"),
    ("clip_014", "commons", 119950449, "Entrevista a una joven participante de una marcha"),
    ("clip_015", "commons", 149445104, "Entrevista a una organizadora de la fiesta patronal de Tayta Palli de Chuyas"),
    ("clip_016", "commons", 149666949, "Testimonio de una pobladora del departamento de San Martín (parte 1)"),
    ("clip_017", "commons", 149666950, "Testimonio de una pobladora del departamento de San Martín (parte 2)"),
    ("clip_018", "archive", "pascoenlima2017",
     "Entrevista en un plantón de familias de Pasco en Lima (Radio Bomba, 2017); ruido de calle"),
    ("clip_019", "archive", "e6ejsht",
     "Entrevista a un dirigente awajún sobre la audiencia del caso Estación 6 (Radio Bomba, 2018)"),
]
OPENSLR_POR_SEXO = 5
OPENSLR_SEMILLA = 2026


def _get(url, params=None, headers=None, intentos=5):
    """GET con User-Agent, pausa de cortesía y reintentos ante 429 o errores 5xx."""
    cab = dict(UA, **(headers or {}))
    for i in range(intentos):
        time.sleep(PAUSA)
        r = requests.get(url, params=params, headers=cab, timeout=180)
        if r.status_code in (200, 206):
            return r
        if r.status_code == 429 or r.status_code >= 500:
            espera = int(r.headers.get("retry-after", 0) or 0) or 10 * (i + 1)
            print(f"   HTTP {r.status_code}, reintento en {espera} s")
            time.sleep(espera)
            continue
        r.raise_for_status()
    r.raise_for_status()


def _limpiar(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html or "")).strip()


def commons_info(pageid, pagina=None, ancho=None):
    """URL del archivo original, licencia y autor. Con `pagina` (DjVu) también la URL de esa página
    renderizada por Commons al `ancho` pedido."""
    p = {"action": "query", "format": "json", "pageids": pageid, "prop": "imageinfo",
         "iiprop": "url|size|mime|extmetadata", "iiextmetadatafilter": "LicenseShortName|LicenseUrl|Artist"}
    if pagina and ancho:
        p.update(iiurlwidth=ancho, iiurlparam=f"page{pagina}-{ancho}px")
    ii = _get(COMMONS_API, p).json()["query"]["pages"][str(pageid)]["imageinfo"][0]
    md = ii.get("extmetadata", {})
    licencia = _limpiar(md.get("LicenseShortName", {}).get("value"))
    return {
        "url": ii["url"].split("?")[0], "url_pagina": ii.get("thumburl"),
        "mime": ii.get("mime"), "bytes": ii.get("size", 0), "ancho": ii.get("width"),
        "licencia": "Dominio público" if licencia.lower() == "public domain" else licencia,
        "licencia_url": _limpiar(md.get("LicenseUrl", {}).get("value")),
        "autor": _limpiar(md.get("Artist", {}).get("value")),
        "fuente_url": f"https://commons.wikimedia.org/?curid={pageid}",
    }


def archive_info(identificador):
    md = _get(f"https://archive.org/metadata/{identificador}").json()["metadata"]
    lic_url = md.get("licenseurl", "")
    anio = str(md.get("date", ""))[:4]
    if "publicdomain/mark" in lic_url:
        licencia = "Dominio público (Public Domain Mark 1.0)"
    elif "by-nc-sa/3.0" in lic_url:
        licencia = "CC BY-NC-SA 3.0"
    elif "by-nc-sa/4.0" in lic_url:
        licencia = "CC BY-NC-SA 4.0"
    elif not lic_url and anio and int(anio) < 1900:
        licencia = f"Dominio público (obra de {anio}, sin restricciones de derechos conocidas)"
    else:
        raise ValueError(f"{identificador}: licencia no reconocida ({lic_url!r}), revisar antes de usar")
    autores = md.get("creator") or ""
    autores = "; ".join(autores) if isinstance(autores, list) else autores
    autores = "" if autores.lower() == "unknown" else autores.replace("radio bomba", "Radio Bomba")
    contribuyente = md.get("contributor", "")
    if contribuyente and contribuyente not in autores:
        autores = f"{autores} (digitalización: {contribuyente})" if autores else contribuyente
    return {"licencia": licencia, "licencia_url": lic_url, "autor": autores or "Desconocido",
            "fuente_url": f"https://archive.org/details/{identificador}"}


# ------------------------------------------- documentos ---------------------------------------
def pagina_pdf(pdf, pagina):
    """Renderiza la página completa (algunos PDF separan el escaneo en capas de fondo y de texto)
    al ancho de su imagen más grande, entre 1600 y LADO_MAX píxeles."""
    with pymupdf.open(pdf) as libro:
        pag = libro[pagina - 1]
        ancho = max((x[2] for x in pag.get_images(full=True)), default=2200)
        zoom = min(max(ancho, 1600), LADO_MAX) / pag.rect.width
        pix = pag.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom))
        return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)


def difuminar_fuera(im, poligono):
    mascara = Image.new("L", im.size, 0)
    ImageDraw.Draw(mascara).polygon([(x * im.width, y * im.height) for x, y in poligono], fill=255)
    return Image.composite(im, im.filter(ImageFilter.GaussianBlur(40)), mascara)


def bajar_documentos():
    originales = RAW_DOC / "originales"
    originales.mkdir(parents=True, exist_ok=True)
    filas = []
    for id_, tipo, pageid, pagina, desc in DOCUMENTOS:
        info = commons_info(pageid)
        es_djvu = info["mime"] == "image/vnd.djvu"
        if es_djvu:   # PyMuPDF no abre DjVu: Commons renderiza la página al ancho original
            info = commons_info(pageid, pagina, info["ancho"])
        destino = RAW_DOC / f"{id_}.jpg"
        if not destino.exists():
            if es_djvu:
                im = Image.open(io.BytesIO(_get(info["url_pagina"]).content))
            else:
                original = originales / f"{id_}{Path(info['url']).suffix.lower()}"
                if not original.exists():
                    print(f"   bajando {id_} ...", flush=True)
                    original.write_bytes(_get(info["url"]).content)
                im = pagina_pdf(original, pagina) if pagina else Image.open(original)
            im = ImageOps.exif_transpose(im).convert("RGB")
            if id_ in CARTELES:
                im = difuminar_fuera(im, CARTELES[id_])
            if id_ in RECORTES:
                x0, y0, x1, y1 = RECORTES[id_]
                im = im.crop((int(x0 * im.width), int(y0 * im.height), int(x1 * im.width), int(y1 * im.height)))
            if max(im.size) > LADO_MAX:
                im.thumbnail((LADO_MAX, LADO_MAX))
            im.save(destino, quality=92)
        if es_djvu:
            detalle = f", página {pagina} del DjVu renderizada por Commons"
        elif pagina:
            detalle = f", PDF completo, página {pagina} renderizada con PyMuPDF"
        else:
            detalle = ", archivo original" + (", recorte de la zona escrita" if id_ in RECORTES else "")
        if id_ in CARTELES:
            detalle += " y difuminado fuera del cartel"
        print(f"{id_} [{tipo}] {destino.name} ({destino.stat().st_size // 1024} KB) - {info['licencia']}")
        filas.append({"id": id_, "modalidad": "documento", "tipo": tipo,
                      "archivo": destino.relative_to(BASE).as_posix(), "repositorio": "Wikimedia Commons",
                      "fuente_url": info["fuente_url"], "licencia": info["licencia"],
                      "licencia_url": info["licencia_url"], "autor": info["autor"], "descripcion": desc,
                      "duracion_seg": "", "acceso": f"descargar_datos.py (API de Commons, pageid={pageid}{detalle})"})
    return filas


# --------------------------------------------- audio ------------------------------------------
def a_wav_16k(origen, destino):
    """Cualquier formato (ogg, opus, mp3, wav) -> WAV PCM mono de 16 kHz con ffmpeg."""
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-i", str(origen),
                    "-ac", "1", "-ar", str(SR), "-c:a", "pcm_s16le", str(destino)], check=True)
    with wave.open(str(destino)) as w:
        return round(w.getnframes() / w.getframerate(), 2)


class ZipRemoto(io.RawIOBase):
    """Archivo remoto leído por partes con HTTP Range: zipfile solo pide los bytes que necesita."""

    BLOQUE = 1 << 20

    def __init__(self, url):
        self.url, self.pos, self.buf_ini, self.buf = url, 0, 0, b""
        r = requests.head(url, headers=UA, allow_redirects=True, timeout=60)
        self.url, self.size = r.url, int(r.headers["Content-Length"])

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, offset, whence=0):
        self.pos = {0: offset, 1: self.pos + offset, 2: self.size + offset}[whence]
        return self.pos

    def read(self, n=-1):
        if n is None or n < 0:
            n = self.size - self.pos
        n = min(n, self.size - self.pos)
        if n <= 0:
            return b""
        fin = self.pos + n
        if not (self.buf_ini <= self.pos and fin <= self.buf_ini + len(self.buf)):
            self.buf_ini = self.pos
            ultimo = min(self.pos + max(n, self.BLOQUE), self.size) - 1
            self.buf = _get(self.url, headers={"Range": f"bytes={self.pos}-{ultimo}"}).content
        datos = self.buf[self.pos - self.buf_ini:fin - self.buf_ini]
        self.pos += len(datos)
        return datos


def bajar_openslr73(primer_numero):
    """Una frase por hablante (6 a 20 palabras), OPENSLR_POR_SEXO hablantes de cada sexo."""
    originales = RAW_AUD / "originales"
    # El texto que leyó cada hablante: sirve para revisar la transcripción manual de la Parte 2,
    # pero no reemplaza esa transcripción manual.
    indice = RAW_AUD / "openslr73_texto_oficial.csv"
    if indice.exists() and all((originales / f"{f['id']}.wav").exists()
                               for f in csv.DictReader(open(indice, encoding="utf-8"))):
        with open(indice, encoding="utf-8") as f:
            oficiales = list(csv.DictReader(f))  # ya elegidos y bajados: no se vuelve a leer el zip
    else:
        oficiales, n = [], primer_numero
        for sexo in ["female", "male"]:
            z = zipfile.ZipFile(ZipRemoto(OPENSLR73.format(sexo=sexo)))
            lineas = z.read("line_index.tsv").decode("utf-8").strip().splitlines()
            frases = [l.split("\t") for l in lineas]
            frases = [(i.strip(), t.strip()) for i, t in frases if 6 <= len(t.split()) <= 20]
            por_hablante = {}
            for i, t in frases:
                por_hablante.setdefault(i.rsplit("_", 1)[0], []).append((i, t))
            rng = random.Random(OPENSLR_SEMILLA)
            hablantes = sorted(por_hablante)
            rng.shuffle(hablantes)
            for h in hablantes[:OPENSLR_POR_SEXO]:
                id_openslr, texto = rng.choice(sorted(por_hablante[h]))
                id_ = f"clip_{n:03d}"
                (originales / f"{id_}.wav").write_bytes(z.read(f"{id_openslr}.wav"))
                oficiales.append({"id": id_, "archivo_openslr": f"{id_openslr}.wav", "hablante_openslr": h,
                                  "sexo": "mujer" if sexo == "female" else "hombre", "texto_oficial": texto})
                n += 1
        with open(indice, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(oficiales[0]))
            w.writeheader()
            w.writerows(oficiales)
    filas = []
    for o in oficiales:
        id_ = o["id"]
        dur = a_wav_16k(originales / f"{id_}.wav", RAW_AUD / f"{id_}.wav")
        zip_ = "es_pe_female.zip" if o["sexo"] == "mujer" else "es_pe_male.zip"
        print(f"{id_} OpenSLR 73 {o['archivo_openslr']} ({dur} s)")
        filas.append({"id": id_, "modalidad": "audio", "tipo": "lectura",
                      "archivo": (RAW_AUD / f"{id_}.wav").relative_to(BASE).as_posix(),
                      "repositorio": "OpenSLR 73", "fuente_url": "https://www.openslr.org/73/",
                      "licencia": "CC BY-SA 4.0", "licencia_url": "https://creativecommons.org/licenses/by-sa/4.0/",
                      "autor": "Google (Guevara-Rukoz et al., 2020)",
                      "descripcion": f"Frase leída en español peruano, hablante anónimo ({o['sexo']})",
                      "duracion_seg": dur,
                      "acceso": f"descargar_datos.py ({zip_}, archivo {o['archivo_openslr']})"})
    return filas


def bajar_audio():
    originales = RAW_AUD / "originales"
    originales.mkdir(parents=True, exist_ok=True)
    filas = []
    for id_, repo, ref, desc in AUDIOS:
        if repo == "commons":
            info = commons_info(ref)
            url = info["url"]
            acceso = f"descargar_datos.py (API de Commons, pageid={ref}, archivo original)"
        else:
            info = archive_info(ref)
            archivos = _get(f"https://archive.org/metadata/{ref}/files").json()["result"]
            mp3 = next(a["name"] for a in archivos if "MP3" in a.get("format", "") and a.get("source") == "original")
            url = f"https://archive.org/download/{ref}/{requests.utils.quote(mp3)}"
            acceso = f"descargar_datos.py (archive.org/details/{ref}, MP3 original)"
        original = originales / f"{id_}{Path(url.split('?')[0]).suffix.lower()}"
        if not original.exists():
            print(f"   bajando {id_} ...", flush=True)
            original.write_bytes(_get(url).content)
        dur = a_wav_16k(original, RAW_AUD / f"{id_}.wav")
        print(f"{id_} {original.name} ({dur} s) - {info['licencia']}")
        filas.append({"id": id_, "modalidad": "audio", "tipo": "entrevista",
                      "archivo": (RAW_AUD / f"{id_}.wav").relative_to(BASE).as_posix(),
                      "repositorio": "Wikimedia Commons" if repo == "commons" else "archive.org (Radio Bomba)",
                      "fuente_url": info["fuente_url"], "licencia": info["licencia"],
                      "licencia_url": info["licencia_url"], "autor": info["autor"], "descripcion": desc,
                      "duracion_seg": dur, "acceso": acceso})
    return filas + bajar_openslr73(len(AUDIOS) + 1)


if __name__ == "__main__":
    hoy = date.today().isoformat()
    filas = bajar_documentos() + bajar_audio()
    for f in filas:
        f["fecha_descarga"] = hoy
    FUENTES.parent.mkdir(parents=True, exist_ok=True)
    with open(FUENTES, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id", "modalidad", "tipo", "archivo", "repositorio", "fuente_url",
                                          "licencia", "licencia_url", "autor", "descripcion", "duracion_seg",
                                          "fecha_descarga", "acceso"])
        w.writeheader()
        w.writerows(filas)
    docs = [f for f in filas if f["modalidad"] == "documento"]
    auds = [f for f in filas if f["modalidad"] == "audio"]
    print(f"\nDocumentos: {len(docs)} -> " + ", ".join(f"{t}: {sum(d['tipo'] == t for d in docs)}"
                                                    for t in ["impreso", "foto", "manuscrito"]))
    print(f"Audio: {len(auds)} clips, {sum(a['duracion_seg'] for a in auds) / 60:.1f} min")
    print(f"Fuentes -> {FUENTES}")
