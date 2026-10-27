"""Inventario de escenas de inundación GFM (Copernicus Global Flood Monitoring) en las ventanas de cada evento.

    .venv/Scripts/python.exe scripts/inventario_gfm.py            # todos los eventos
    .venv/Scripts/python.exe scripts/inventario_gfm.py 2023       # solo uno; conserva las filas de los demás

GFM procesa cada imagen radar Sentinel-1 (20 m) con tres algoritmos (DLR, TUW, LIST) y publica un
mapa "ensemble" de agua inundada. EODC lo sirve en un catálogo STAC abierto, sin cuenta:
https://stac.eodc.eu/api/v1, colección GFM. Cada escena cubre un tile Equi7 de 300 x 300 km.

Ventanas del estudio:
- Niño Costero 2017: diciembre 2016 a mayo 2017.
- Niño Costero 2023 (con el ciclón Yaku): enero a junio 2023. Se amplió desde abril porque el agua en
  Piura seguía creciendo el 27 de abril; junio además coincide con el periodo de los datos de INDECI 2023.
- Referencia 2022: enero a junio de un año sin Niño (condiciones frías en la costa), para separar
  el agua habitual (arrozales, salinas, lagunas estacionales) de la inundación de cada evento.

Escribe datos/procesados/gfm_inventario.csv: una fila por escena con la fecha (UTC y hora de Perú),
el tile, los píxeles inundados y "inundables" que reporta GFM para todo el tile y los enlaces a los
rasters (extensión de inundación, máscara de exclusión, agua de referencia y alertas de calidad).
Los píxeles son del tile completo, que excede el área de estudio: sirven para ubicar fechas, no para medir.
"""
import sys
from datetime import timedelta
from pathlib import Path

import geopandas as gpd
import pandas as pd
from pystac_client import Client

BASE = Path(__file__).resolve().parent.parent
PROC = BASE / "datos" / "procesados"
STAC = "https://stac.eodc.eu/api/v1"
VENTANAS = {"2017": "2016-12-01/2017-05-31", "2023": "2023-01-01/2023-06-30", "2022": "2022-01-01/2022-06-30"}
ASSETS = ["ensemble_flood_extent", "exclusion_mask", "reference_water_mask", "advisory_flags"]
PIXEL_KM2 = 20 * 20 / 1e6


def main():
    zona = gpd.read_file(PROC / "departamentos_estudio.geojson").union_all().simplify(0.05)
    cliente = Client.open(STAC)

    filas = []
    eventos = sys.argv[1:] or list(VENTANAS)
    for evento, ventana in ((e, VENTANAS[e]) for e in eventos):
        busqueda = cliente.search(collections=["GFM"], intersects=zona, datetime=ventana)
        for item in busqueda.items():
            p = item.properties
            utc = pd.Timestamp(p["datetime"])
            filas.append({
                "evento": evento,
                "item_id": item.id,
                "fecha_utc": utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "fecha_peru": (utc - timedelta(hours=5)).strftime("%Y-%m-%d"),
                "tile": p.get("Equi7Tile"),
                "flooded_pixels": p.get("flooded_pixels"),
                "floodable_pixels": p.get("floodable_pixels"),
                "anomaly_detected": p.get("anomaly_detected"),
                **{f"url_{a}": item.assets[a].href for a in ASSETS if a in item.assets},
            })

    inv = pd.DataFrame(filas)
    inv["inundado_tile_km2"] = inv["flooded_pixels"] * PIXEL_KM2
    salida = PROC / "gfm_inventario.csv"
    if salida.exists():  # conserva los eventos que no se consultaron en esta corrida
        previa = pd.read_csv(salida, dtype={"evento": str})
        inv = pd.concat([previa[~previa["evento"].isin(eventos)], inv], ignore_index=True)
    inv = inv.sort_values(["evento", "fecha_utc", "tile"]).reset_index(drop=True)
    inv.to_csv(salida, index=False, encoding="utf-8")

    for evento, g in inv.groupby("evento"):
        print(f"\n== {evento}: {len(g)} escenas, {g['fecha_peru'].nunique()} fechas, tiles {sorted(g['tile'].unique())}")
        print(g.groupby("tile")["fecha_peru"].nunique().rename("fechas_por_tile").to_string())
        top = g.groupby("fecha_peru")["inundado_tile_km2"].sum().sort_values(ascending=False).head(8)
        print("Fechas con más agua detectada (suma de tiles, km²):")
        print(top.round(1).to_string())


if __name__ == "__main__":
    main()
