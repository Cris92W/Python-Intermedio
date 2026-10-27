"""Límites distritales y provinciales del departamento de Piura, y contorno del Perú para el mapa de ubicación.

    .venv/Scripts/python.exe scripts/obtener_limites.py

Fuente: límite distrital INEI 2020 (1874 distritos), redistribuido por GeoGPS Perú y publicado
en el dataset del curso en Hugging Face (aquiro1994/ds-python-up, _data/LIMITE_DISTRITAL_2020_INEI.zip).

Escribe:
- datos/procesados/distritos_estudio.gpkg: un polígono por distrito de Piura con UBIGEO, nombres y área en km².
- datos/procesados/departamentos_estudio.geojson: Piura disuelto y simplificado (área de búsqueda de imágenes).
- web/data/provincias.geojson: las 8 provincias de Piura, para los mapas.
- web/data/peru.geojson: los 25 departamentos muy simplificados, para el mapa de ubicación.
"""
from pathlib import Path

import geopandas as gpd
import requests

BASE = Path(__file__).resolve().parent.parent
ORIG = BASE / "datos" / "originales" / "limites_inei"
PROC = BASE / "datos" / "procesados"
WEB = BASE / "web" / "data"
URL = ("https://huggingface.co/datasets/aquiro1994/ds-python-up/resolve/main/"
       "_data/LIMITE_DISTRITAL_2020_INEI.zip")
ZIP = ORIG / "LIMITE_DISTRITAL_2020_INEI.zip"

DEPARTAMENTOS = {"20": "PIURA"}
# Albers equal-area de Sudamérica: las áreas no se calculan en EPSG:4326.
CRS_AREA = "ESRI:102033"


def descargar():
    if ZIP.exists():
        return
    ORIG.mkdir(parents=True, exist_ok=True)
    r = requests.get(URL, timeout=300,
                     headers={"User-Agent": "tarea3-unmsm (https://github.com/Cris92W/Python-Intermedio)"})
    r.raise_for_status()
    ZIP.write_bytes(r.content)


def main():
    descargar()
    todos = gpd.read_file(f"zip://{ZIP.as_posix()}")
    distritos = todos[todos["CCDD"].isin(DEPARTAMENTOS)].copy()
    distritos = distritos[["UBIGEO", "CCDD", "NOMBDEP", "NOMBPROV", "NOMBDIST", "geometry"]]
    distritos["NOMBDEP"] = distritos["CCDD"].map(DEPARTAMENTOS)
    # El archivo trae "PARIÑAS": un carácter de control sobrante de la conversión de codificación.
    distritos["NOMBDIST"] = distritos["NOMBDIST"].str.replace("", "", regex=False)
    distritos["area_km2"] = distritos.to_crs(CRS_AREA).area / 1e6
    distritos = distritos.sort_values("UBIGEO").reset_index(drop=True)

    PROC.mkdir(parents=True, exist_ok=True)
    WEB.mkdir(parents=True, exist_ok=True)
    distritos.to_file(PROC / "distritos_estudio.gpkg", layer="distritos", driver="GPKG")

    departamentos = distritos.dissolve(by=["CCDD", "NOMBDEP"], as_index=False, aggfunc={"area_km2": "sum"})
    departamentos["n_distritos"] = distritos.groupby("CCDD").size().reindex(departamentos["CCDD"]).values
    departamentos["geometry"] = departamentos.geometry.simplify(0.002, preserve_topology=True)
    departamentos.to_file(PROC / "departamentos_estudio.geojson", driver="GeoJSON")

    provincias = distritos.dissolve(by="NOMBPROV", as_index=False, aggfunc={"area_km2": "sum"})
    provincias["geometry"] = provincias.geometry.simplify(0.003, preserve_topology=True)
    rotulo = provincias.to_crs("EPSG:32717").representative_point().to_crs(4326)  # siempre cae dentro
    provincias["lab_x"], provincias["lab_y"] = rotulo.x.round(3), rotulo.y.round(3)
    provincias[["NOMBPROV", "area_km2", "lab_x", "lab_y", "geometry"]].round({"area_km2": 1}).to_file(
        WEB / "provincias.geojson", driver="GeoJSON", COORDINATE_PRECISION=4)

    peru = todos.dissolve(by="CCDD", as_index=False)[["CCDD", "geometry"]]
    peru["geometry"] = peru.geometry.simplify(0.06, preserve_topology=True)
    peru.to_file(WEB / "peru.geojson", driver="GeoJSON", COORDINATE_PRECISION=2)

    print(departamentos[["CCDD", "NOMBDEP", "n_distritos", "area_km2"]].round(0).to_string(index=False))
    print(provincias[["NOMBPROV", "area_km2"]].round(0).to_string(index=False))
    print(f"Total: {len(distritos)} distritos, {distritos['area_km2'].sum():,.0f} km²")


if __name__ == "__main__":
    main()
