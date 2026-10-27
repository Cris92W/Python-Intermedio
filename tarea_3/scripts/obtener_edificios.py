"""Huellas de edificios de Microsoft (Global ML Building Footprints) para la zona de detalle de Piura.

    .venv/Scripts/python.exe scripts/obtener_edificios.py

Microsoft detecta los techos con aprendizaje automático sobre imágenes satelitales (Bing/Maxar, varios
años) y publica un polígono por edificio, partido en tiles de nivel 9 (quadkeys). Licencia ODbL.
https://github.com/microsoft/GlobalMLBuildingFootprints

Zona de detalle: Piura, Castilla, Veintiséis de Octubre y el Bajo Piura (Catacaos, Cura Mori,
El Tallán), inundados por el desborde del río Piura en 2017.

Escribe datos/originales/edificios_microsoft/piura.gpkg con los edificios dentro de la zona.
"""
import gzip
import io
import json
import math
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import box, shape

BASE = Path(__file__).resolve().parent.parent
DESTINO = BASE / "datos" / "originales" / "edificios_microsoft"
ENLACES = "https://minedbuildings.z5.web.core.windows.net/global-buildings/dataset-links.csv"
CABECERAS = {"User-Agent": "tarea3-unmsm (https://github.com/Cris92W/Python-Intermedio)"}

ZONAS = {  # (oeste, sur, este, norte)
    "piura": (-80.80, -5.45, -80.58, -5.12),
}


def quadkey(lon, lat, z=9):
    x = (lon + 180) / 360
    s = math.sin(math.radians(lat))
    y = 0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)
    tx, ty = int(x * 2 ** z), int(y * 2 ** z)
    return "".join(str((1 if tx & (1 << (i - 1)) else 0) + (2 if ty & (1 << (i - 1)) else 0))
                   for i in range(z, 0, -1))


def main():
    enlaces = pd.read_csv(ENLACES, dtype={"QuadKey": str})
    enlaces = enlaces[enlaces["Location"] == "Peru"]
    DESTINO.mkdir(parents=True, exist_ok=True)

    for zona, (o, s, e, n) in ZONAS.items():
        salida = DESTINO / f"{zona}.gpkg"
        if salida.exists():
            print(f"{zona}: ya existe")
            continue
        claves = {quadkey(lon, lat) for lon in (o, e) for lat in (s, n)}
        caja = box(o, s, e, n)
        geoms, alturas = [], []
        for url in enlaces[enlaces["QuadKey"].isin(claves)]["Url"]:
            crudo = requests.get(url, headers=CABECERAS, timeout=600).content
            with gzip.open(io.BytesIO(crudo), "rt") as f:
                for linea in f:
                    rasgo = json.loads(linea)
                    g = shape(rasgo["geometry"])
                    if g.intersects(caja):
                        geoms.append(g)
                        alturas.append(rasgo["properties"].get("height", -1))
        gdf = gpd.GeoDataFrame({"altura_ms": alturas}, geometry=geoms, crs="EPSG:4326")
        gdf.to_file(salida, driver="GPKG")
        print(f"{zona}: {len(gdf):,} edificios de los quadkeys {sorted(claves)}; "
              f"con altura estimada: {(gdf['altura_ms'] > 0).sum():,}")


if __name__ == "__main__":
    main()
