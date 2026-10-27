"""Superficie inundada por distrito y fecha según GFM, para los Niños Costeros de 2017 y 2023.

    .venv/Scripts/python.exe scripts/procesar_gfm.py            # todos los eventos del inventario
    .venv/Scripts/python.exe scripts/procesar_gfm.py 2022       # solo uno (reemplaza sus filas)

Lee las escenas de datos/procesados/gfm_inventario.csv (las crea scripts/inventario_gfm.py) directamente
desde el catálogo abierto de EODC, sin descargarlas: son COG y se lee solo la vista general de 80 m
(factor 4 sobre los 20 m originales), que basta para medir superficies por distrito.

Valores del mapa "ensemble_flood_extent" de GFM: 1 = inundado, 0 = observado sin inundación,
255 = sin dato (fuera de la pasada o zona excluida). El agua permanente y estacional (máscara de
agua de referencia mensual) ya está descontada por GFM, por eso no se resta aquí.

Para no contar dos veces, las escenas de una misma fecha y tile se combinan píxel a píxel antes de contar.

Escribe:
- datos/procesados/gfm_distrito_fecha.csv: evento, fecha (hora de Perú), UBIGEO, km² inundados y km²
  observados por el radar ese día.
- datos/procesados/gfm_80m/{evento}_{tile}.tif: por píxel, cuántas fechas estuvo inundado (0 = nunca)
  y en la banda 2 cuántas fechas fue observado. Sirven para el mapa de máxima extensión.
"""
import os

os.environ.update(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",
                  GDAL_HTTP_MULTIPLEX="YES", GDAL_HTTP_VERSION="2",
                  GDAL_HTTP_MERGE_CONSECUTIVE_RANGES="YES", VSI_CACHE="TRUE",
                  GDAL_HTTP_MAX_RETRY="4", GDAL_HTTP_RETRY_DELAY="3")

import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize
from rasterio.transform import Affine

BASE = Path(__file__).resolve().parent.parent
PROC = BASE / "datos" / "procesados"
SALIDA_RASTER = PROC / "gfm_80m"
FACTOR = 4                       # 20 m -> 80 m
PIXEL_KM2 = (20 * FACTOR) ** 2 / 1e6
HILOS = 6


def grilla_tile(url, distritos):
    """Grilla de 80 m del tile y raster de índices de distrito (0 = fuera del estudio)."""
    with rasterio.open(url) as ds:
        crs, transform, alto, ancho = ds.crs, ds.transform, ds.height // FACTOR, ds.width // FACTOR
    transform = transform * Affine.scale(FACTOR)
    geoms = distritos.to_crs(crs)
    indices = rasterize(((g, i + 1) for i, g in enumerate(geoms.geometry)), out_shape=(alto, ancho),
                        transform=transform, fill=0, dtype="uint16")
    return {"crs": crs, "transform": transform, "shape": (alto, ancho), "indices": indices}


def leer_fecha(urls, forma):
    """Combina las escenas de una fecha y tile: inundado si alguna lo marca, observado si alguna lo vio."""
    inundado = np.zeros(forma, dtype=bool)
    observado = np.zeros(forma, dtype=bool)
    for url in urls:
        with rasterio.open(url) as ds:
            a = ds.read(1, out_shape=forma)
        inundado |= a == 1
        observado |= a != 255
    return inundado, observado


def main():
    inv = pd.read_csv(PROC / "gfm_inventario.csv", dtype={"evento": str})
    eventos = sys.argv[1:] or sorted(inv["evento"].unique())
    inv = inv[inv["evento"].isin(eventos)]
    distritos = gpd.read_file(PROC / "distritos_estudio.gpkg")
    n = len(distritos)
    SALIDA_RASTER.mkdir(parents=True, exist_ok=True)

    grillas = {}
    for tile, g in inv.groupby("tile"):
        grillas[tile] = grilla_tile(g["url_ensemble_flood_extent"].iloc[0], distritos)
        print(f"grilla {tile}: {int((grillas[tile]['indices'] > 0).sum() * PIXEL_KM2):,} km² del estudio")

    acumulados = {}
    candado = threading.Lock()
    grupos = list(inv.groupby(["evento", "fecha_peru", "tile"])["url_ensemble_flood_extent"])
    filas = []

    def procesar(clave, urls):
        evento, fecha, tile = clave
        grilla = grillas[tile]
        inundado, observado = leer_fecha(list(urls), grilla["shape"])
        idx = grilla["indices"]
        km2_inund = np.bincount(idx[inundado], minlength=n + 1)[1:] * PIXEL_KM2
        km2_obs = np.bincount(idx[observado], minlength=n + 1)[1:] * PIXEL_KM2
        with candado:
            frec, obs = acumulados.setdefault((evento, tile), (np.zeros(grilla["shape"], np.uint16),
                                                               np.zeros(grilla["shape"], np.uint16)))
            frec += inundado
            obs += observado
        return [{"evento": evento, "fecha_peru": fecha, "tile": tile, "UBIGEO": distritos.at[i, "UBIGEO"],
                 "inundado_km2": km2_inund[i], "observado_km2": km2_obs[i]}
                for i in np.flatnonzero(km2_obs)]

    inicio = time.time()
    with ThreadPoolExecutor(HILOS) as pool:
        futuros = {pool.submit(procesar, k, u): k for k, u in grupos}
        for j, fut in enumerate(as_completed(futuros), 1):
            try:
                filas.extend(fut.result())
            except Exception as e:  # una escena caída no detiene el resto; queda registrada
                print(f"ERROR {futuros[fut]}: {e}")
            if j % 25 == 0:
                print(f"{j}/{len(grupos)} grupos, {time.time() - inicio:.0f} s", flush=True)

    # Un distrito puede caer en dos tiles: se suman (los tiles Equi7 no se superponen).
    tabla = (pd.DataFrame(filas).groupby(["evento", "fecha_peru", "UBIGEO"], as_index=False)
             [["inundado_km2", "observado_km2"]].sum())
    salida = PROC / "gfm_distrito_fecha.csv"
    if salida.exists():  # conserva los eventos que no se procesaron en esta corrida
        previa = pd.read_csv(salida, dtype={"evento": str, "UBIGEO": str})
        tabla = pd.concat([previa[~previa["evento"].isin(eventos)], tabla], ignore_index=True)
    tabla.sort_values(["evento", "fecha_peru", "UBIGEO"]).to_csv(salida, index=False, encoding="utf-8")

    for (evento, tile), (frec, obs) in acumulados.items():
        g = grillas[tile]
        perfil = dict(driver="GTiff", width=g["shape"][1], height=g["shape"][0], count=2, dtype="uint16",
                      crs=g["crs"], transform=g["transform"], compress="deflate", tiled=True)
        with rasterio.open(SALIDA_RASTER / f"{evento}_{tile}.tif", "w", **perfil) as dst:
            dst.write(frec, 1)
            dst.write(obs, 2)
    print(f"Listo en {time.time() - inicio:.0f} s: {len(tabla)} filas distrito-fecha")


if __name__ == "__main__":
    main()
