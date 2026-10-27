"""Recursos del reel que no van al repositorio: mapa base, tipografías y música.

Uso (desde tarea_3/reel):  ../../PRACTICA_2/.venv/Scripts/python preparar.py
Escribe:
- recursos/base.jpg y base.json: mosaico de Esri World Imagery sobre Piura, en Web Mercator como las capas de agua
  del dashboard (base.json guarda el zoom y el origen, para ubicar coordenadas en píxeles).
- recursos/fuentes/: Archivo e IBM Plex Mono, las tipografías del dashboard (Google Fonts, licencia OFL).
- recursos/floating_cities.mp3: «Floating Cities», Kevin MacLeod (incompetech.com), licencia CC BY 4.0.
Lo ya descargado no se vuelve a pedir.
"""
import io
import json
import math
from pathlib import Path

import requests
from PIL import Image

AQUI = Path(__file__).resolve().parent
REC = AQUI / "recursos"
Z = 10                                    # unos 150 m por píxel: alcanza para el acercamiento a Sechura
CAJA = (-81.75, -6.75, -78.85, -3.75)     # Piura con margen de mar al oeste
URL = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
GF = "https://github.com/google/fonts/raw/main/ofl"
DESCARGAS = {
    "fuentes/Archivo.ttf": f"{GF}/archivo/Archivo%5Bwdth,wght%5D.ttf",
    "fuentes/IBMPlexMono-Medium.ttf": f"{GF}/ibmplexmono/IBMPlexMono-Medium.ttf",
    "fuentes/OFL.txt": f"{GF}/archivo/OFL.txt",
    "floating_cities.mp3": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Floating%20Cities.mp3",
}


def tesela(lon, lat, z):
    """Coordenada de tesela (con decimales) de un punto."""
    n = 2 ** z
    y = (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2
    return (lon + 180) / 360 * n, y * n


def main():
    (REC / "fuentes").mkdir(parents=True, exist_ok=True)
    for destino, url in DESCARGAS.items():
        if not (REC / destino).exists():
            r = requests.get(url, timeout=120)
            r.raise_for_status()
            (REC / destino).write_bytes(r.content)
    (REC / "teselas").mkdir(parents=True, exist_ok=True)
    x0, y0 = (int(v) for v in tesela(CAJA[0], CAJA[3], Z))
    x1, y1 = (int(v) for v in tesela(CAJA[2], CAJA[1], Z))
    base = Image.new("RGB", ((x1 - x0 + 1) * 256, (y1 - y0 + 1) * 256))
    ses = requests.Session()
    ses.headers["User-Agent"] = "tarea3-unmsm (https://github.com/Cris92W/Python-Intermedio)"
    for x in range(x0, x1 + 1):
        for y in range(y0, y1 + 1):
            f = REC / "teselas" / f"{Z}_{x}_{y}.jpg"
            if not f.exists():
                r = ses.get(URL.format(z=Z, x=x, y=y), timeout=60)
                r.raise_for_status()
                f.write_bytes(r.content)
            base.paste(Image.open(io.BytesIO(f.read_bytes())).convert("RGB"), ((x - x0) * 256, (y - y0) * 256))
    base.save(REC / "base.jpg", quality=92)
    (REC / "base.json").write_text(json.dumps({"z": Z, "x0": x0, "y0": y0, "ancho": base.width, "alto": base.height}), encoding="utf-8")
    print(f"base.jpg: {base.width} × {base.height} px, {(x1 - x0 + 1) * (y1 - y0 + 1)} teselas de zoom {Z}")


if __name__ == "__main__":
    main()
