"""Imágenes del agua detectada por el radar en Piura, para superponer en los mapas de la web.

    .venv/Scripts/python.exe scripts/mapas_agua.py

Parte de los rasters de 80 m de scripts/procesar_gfm.py (banda 1: fechas con agua en cada píxel):
- agua_2017.png y agua_2023.png: inundación anómala, es decir, píxeles con agua en al menos dos fechas
  del evento que en la referencia de 2022 nunca tuvieron agua. El color dice en cuántas fechas se vio agua.
- agua_2022.png: agua habitual, con agua en al menos dos fechas de ene-jun 2022 (año sin Niño).

Las imágenes se reproyectan a Web Mercator (EPSG:3857), la proyección de MapLibre, a 100 m, y se recortan
al departamento. Escribe web/data/agua_{evento}.png y web/data/agua.json con las esquinas de la imagen.
"""
import os

os.environ["GDAL_PAM_ENABLED"] = "NO"  # sin archivos .aux.xml junto a los PNG

import json
import warnings
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.errors import NotGeoreferencedWarning
from rasterio.features import rasterize
from rasterio.transform import from_origin
from rasterio.warp import Resampling, reproject

BASE = Path(__file__).resolve().parent.parent
PROC = BASE / "datos" / "procesados"
WEB = BASE / "web" / "data"
RES = 100  # metros en Web Mercator
REFERENCIA = "2022"
# Fechas con agua -> color (RGBA). Celestes que se leen sobre imagen satelital y sobre fondo oscuro.
CLASES = [(2, 3, (166, 232, 255, 170)), (4, 7, (84, 196, 245, 205)), (8, 15, (32, 140, 230, 230)),
          (16, 999, (24, 82, 196, 245))]
HABITUAL = (226, 232, 236, 200)


def grilla(departamento):
    o, s, e, n = departamento.to_crs(3857).total_bounds
    o, s, e, n = (np.floor(o / RES) * RES, np.floor(s / RES) * RES, np.ceil(e / RES) * RES, np.ceil(n / RES) * RES)
    return from_origin(o, n, RES, RES), (int((n - s) / RES), int((e - o) / RES)), (o, s, e, n)


def mosaico(evento, transform, forma, anomalo):
    """Fechas con agua por píxel en la grilla Mercator (0 = nunca o descartado)."""
    salida = np.zeros(forma, dtype="uint16")
    for tif in sorted((PROC / "gfm_80m").glob(f"{evento}_*.tif")):
        with rasterio.open(tif) as ds:
            frec = ds.read(1)
            frec[frec < 2] = 0
            if anomalo:
                with rasterio.open(tif.parent / tif.name.replace(evento, REFERENCIA, 1)) as ref:
                    frec[ref.read(1) > 0] = 0
            destino = np.zeros(forma, dtype="uint16")
            reproject(frec, destino, src_transform=ds.transform, src_crs=ds.crs, dst_transform=transform,
                      dst_crs="EPSG:3857", resampling=Resampling.max)
        salida = np.maximum(salida, destino)
    return salida


def guardar_png(rgba, nombre):
    # Un PNG sin georreferencia es lo esperado: las esquinas van en agua.json.
    warnings.filterwarnings("ignore", category=NotGeoreferencedWarning)
    with rasterio.open(WEB / nombre, "w", driver="PNG", width=rgba.shape[2], height=rgba.shape[1],
                       count=4, dtype="uint8") as dst:
        dst.write(rgba)


def main():
    departamento = gpd.read_file(PROC / "departamentos_estudio.geojson")
    transform, forma, (o, s, e, n) = grilla(departamento)
    dentro = rasterize(departamento.to_crs(3857).geometry, out_shape=forma, transform=transform,
                       fill=0, dtype="uint8").astype(bool)

    for evento, anomalo in (("2017", True), ("2023", True), (REFERENCIA, False)):
        frec = mosaico(evento, transform, forma, anomalo)
        frec[~dentro] = 0
        rgba = np.zeros((4, *forma), dtype="uint8")
        if anomalo:
            for desde, hasta, color in CLASES:
                sel = (frec >= desde) & (frec <= hasta)
                rgba[:, sel] = np.array(color, dtype="uint8")[:, None]
        else:
            rgba[:, frec > 0] = np.array(HABITUAL, dtype="uint8")[:, None]
        guardar_png(rgba, f"agua_{evento}.png")
        km2 = float((frec > 0).sum() * RES * RES / 1e6)
        print(f"agua_{evento}.png: {(WEB / f'agua_{evento}.png').stat().st_size / 1e3:.0f} kB, "
              f"{km2:.0f} km² en Mercator (sin corregir; solo para dibujar)")

    a_geo = Transformer.from_crs(3857, 4326, always_xy=True)
    esquinas = [list(np.round(a_geo.transform(x, y), 5)) for x, y in ((o, n), (e, n), (e, s), (o, s))]
    (WEB / "agua.json").write_text(json.dumps({
        "esquinas": esquinas, "resolucion_m": RES,
        "clases": [{"desde": d, "hasta": h, "color": f"rgba({c[0]},{c[1]},{c[2]},{c[3] / 255:.2f})"}
                   for d, h, c in CLASES],
        "habitual": f"rgba({HABITUAL[0]},{HABITUAL[1]},{HABITUAL[2]},{HABITUAL[3] / 255:.2f})",
    }, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
