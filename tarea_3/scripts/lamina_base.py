"""Imagen satelital de fondo para la lámina de portada: Sentinel-2 cloudless 2016 de EOX, recortada a la lámina.

    .venv/Scripts/python.exe scripts/lamina_base.py

El mosaico sin nubes de EOX (https://s2maps.eu) combina escenas Sentinel-2 de 2016, un año antes del primer Niño
del estudio: el desierto de Sechura aparece seco y el agua del radar resalta sobre él. La edición 2016 tiene
licencia CC BY 4.0 («Sentinel-2 cloudless – https://s2maps.eu by EOX IT Services GmbH (Contains modified
Copernicus Sentinel data 2016)»), así que la imagen puede guardarse y publicarse con el dashboard.

Escribe web/data/lamina.jpg: Web Mercator, la misma caja B de lamina() en app.js, 1200 px de ancho.
"""
import io
import math
from pathlib import Path

import numpy as np
import requests
from PIL import Image, ImageEnhance, ImageFilter

BASE = Path(__file__).resolve().parent.parent
SALIDA = BASE / "web" / "data" / "lamina.jpg"
CAJA = (-82.25, -6.50, -79.05, -3.96)   # oeste, sur, este, norte: la caja B de lamina() en app.js
# El margen de mar al oeste deja lugar al mapa de ubicación (abajo a la izquierda) sin tapar la costa de Piura
Z, ANCHO = 10, 1200
URL = "https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless_3857/default/g/{z}/{y}/{x}.jpg"


def tesela(lon, lat):
    """Coordenada de tesela (con decimales) de un punto, a zoom Z."""
    n = 2 ** Z
    y = (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2
    return (lon + 180) / 360 * n, y * n


def main():
    (fx0, fy0), (fx1, fy1) = tesela(CAJA[0], CAJA[3]), tesela(CAJA[2], CAJA[1])
    x0, y0, x1, y1 = int(fx0), int(fy0), int(fx1), int(fy1)
    mosaico = Image.new("RGB", ((x1 - x0 + 1) * 256, (y1 - y0 + 1) * 256))
    ses = requests.Session()
    ses.headers["User-Agent"] = "tarea3-unmsm (https://github.com/Cris92W/Python-Intermedio)"
    for x in range(x0, x1 + 1):
        for y in range(y0, y1 + 1):
            r = ses.get(URL.format(z=Z, x=x, y=y), timeout=60)
            r.raise_for_status()
            mosaico.paste(Image.open(io.BytesIO(r.content)).convert("RGB"), ((x - x0) * 256, (y - y0) * 256))
    caja = ((fx0 - x0) * 256, (fy0 - y0) * 256, (fx1 - x0) * 256, (fy1 - y0) * 256)
    alto = round(ANCHO * (caja[3] - caja[1]) / (caja[2] - caja[0]))
    img = mosaico.resize((ANCHO, alto), Image.LANCZOS, box=caja)
    # Un poco más oscura y sobria que el original, para que el agua del radar y los rótulos resalten
    img = ImageEnhance.Brightness(ImageEnhance.Color(img).enhance(0.85)).enhance(0.82)
    # Fuera de las franjas de Sentinel-2 el mosaico rellena el mar con un azul plano (borde festoneado):
    # se pinta con el tono del mar real, con el borde suavizado
    px = np.asarray(img).astype(np.int16)
    relleno = np.abs(px - px[img.height // 2, 2]).sum(axis=2) < 14
    mascara = Image.fromarray((relleno * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(3))
    img = Image.composite(Image.new("RGB", img.size, (23, 32, 41)), img, mascara)
    img.save(SALIDA, quality=84, optimize=True, progressive=True)
    print(f"{SALIDA.name}: {ANCHO} × {alto} px, {SALIDA.stat().st_size / 1e3:.0f} kB, {(x1 - x0 + 1) * (y1 - y0 + 1)} teselas")


if __name__ == "__main__":
    main()
