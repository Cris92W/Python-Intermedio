"""Límites distritales y provinciales del departamento de Piura, y contorno del Perú para el mapa de ubicación.

    .venv/Scripts/python.exe scripts/obtener_limites.py

Fuente: límite distrital INEI 2020 (1874 distritos), redistribuido por GeoGPS Perú y publicado
en el dataset del curso en Hugging Face (aquiro1994/ds-python-up, _data/LIMITE_DISTRITAL_2020_INEI.zip).

Escribe:
- datos/procesados/distritos_estudio.gpkg: un polígono por distrito de Piura con UBIGEO, nombres y área en km².
- datos/procesados/departamentos_estudio.geojson: Piura disuelto y simplificado (área de búsqueda de imágenes).
- datos/procesados/distritos_web.gpkg: los distritos de Piura simplificados para la web (los usa analizar_datos.py).
- web/data/provincias.geojson: las 8 provincias de Piura, para los mapas.
- web/data/peru.geojson: los 25 departamentos, para el contexto y el mapa de ubicación.

Geometría de la web: los 1874 distritos se simplifican como una cobertura (shapely.coverage_simplify), así cada
borde compartido se simplifica una sola vez. Las provincias y el contorno de Piura salen de disolver esos mismos
distritos, de modo que las tres capas calzan vértice por vértice en todos los mapas. Los demás departamentos
se simplifican más, porque solo dan contexto; su diferencia con el borde de Piura queda bajo el trazo de este.
"""
from pathlib import Path

import geopandas as gpd
import requests
import shapely

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
TOL_FINO = 60     # m: distritos, provincias y contorno de Piura
TOL_PERU = 1000   # m: los otros departamentos


def descargar():
    if ZIP.exists():
        return
    ORIG.mkdir(parents=True, exist_ok=True)
    r = requests.get(URL, timeout=300,
                     headers={"User-Agent": "tarea3-unmsm (https://github.com/Cris92W/Python-Intermedio)"})
    r.raise_for_status()
    ZIP.write_bytes(r.content)


def limpiar(geom, parte_m2=1e6, hueco_m2=10e6):
    """Repara un polígono en metros y le quita las partes menores a 1 km² y los huecos menores a 10 km²."""
    geom = shapely.make_valid(geom)
    partes = [p for p in getattr(geom, "geoms", [geom]) if p.geom_type in ("Polygon", "MultiPolygon")]
    partes = [q for p in partes for q in getattr(p, "geoms", [p]) if q.area >= parte_m2]
    limpias = [shapely.Polygon(p.exterior, [r for r in p.interiors if shapely.Polygon(r).area >= hueco_m2]) for p in partes]
    return limpias[0] if len(limpias) == 1 else shapely.MultiPolygon(limpias)


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

    # Cobertura nacional simplificada en metros; vuelve a EPSG:4326 con las mismas coordenadas en los bordes compartidos
    plano = todos.to_crs(CRS_AREA)
    simple = gpd.GeoSeries(shapely.coverage_simplify(plano.geometry.values, tolerance=TOL_FINO),
                           index=plano.index, crs=CRS_AREA).to_crs(4326)
    web = gpd.GeoDataFrame(todos[["UBIGEO", "CCDD", "NOMBPROV"]], geometry=simple)
    web_piura = web[web["CCDD"].isin(DEPARTAMENTOS)].sort_values("UBIGEO")
    web_piura[["UBIGEO", "geometry"]].to_file(PROC / "distritos_web.gpkg", layer="distritos", driver="GPKG")

    provincias = web_piura.dissolve(by="NOMBPROV", as_index=False)[["NOMBPROV", "geometry"]]
    provincias["area_km2"] = provincias["NOMBPROV"].map(distritos.groupby("NOMBPROV")["area_km2"].sum()).round(1)
    rotulo = provincias.to_crs("EPSG:32717").representative_point().to_crs(4326)  # siempre cae dentro
    provincias["lab_x"], provincias["lab_y"] = rotulo.x.round(3), rotulo.y.round(3)
    provincias[["NOMBPROV", "area_km2", "lab_x", "lab_y", "geometry"]].to_file(
        WEB / "provincias.geojson", driver="GeoJSON", COORDINATE_PRECISION=5)

    # Departamentos: Piura con el detalle de sus distritos; los demás, más simplificados. Junín, Lima y Puno quedan
    # inválidos al disolver (bordes del INEI que no calzan entre distritos) y se reparan antes de simplificar.
    peru = web.dissolve(by="CCDD", as_index=False)[["CCDD", "geometry"]]
    resto = peru.to_crs(CRS_AREA)
    resto["geometry"] = resto.geometry.apply(limpiar)
    resto["geometry"] = shapely.coverage_simplify(resto.geometry.values, tolerance=TOL_PERU)
    resto = resto.to_crs(4326)
    resto["geometry"] = shapely.set_precision(resto.geometry.values, 0.001)  # 110 m bastan para el contexto
    es_piura = peru["CCDD"].isin(DEPARTAMENTOS).values
    peru.loc[~es_piura, "geometry"] = resto.loc[~es_piura, "geometry"]
    peru.to_file(WEB / "peru.geojson", driver="GeoJSON", COORDINATE_PRECISION=5)

    print(departamentos[["CCDD", "NOMBDEP", "n_distritos", "area_km2"]].round(0).to_string(index=False))
    print(provincias[["NOMBPROV", "area_km2"]].round(0).to_string(index=False))
    print(f"Total: {len(distritos)} distritos, {distritos['area_km2'].sum():,.0f} km²")


if __name__ == "__main__":
    main()
