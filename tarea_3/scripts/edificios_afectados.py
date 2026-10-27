"""Edificios afectados por inundaciones y huaicos en las zonas de detalle (Piura y Trujillo), 2017 y 2023.

    .venv/Scripts/python.exe scripts/edificios_afectados.py

Cruza cada edificio de Microsoft (scripts/obtener_edificios.py) con tres fuentes independientes:
1. Copernicus EMS 2017 (scripts/obtener_ems_2017.py): polígonos delimitados a mano sobre imágenes de
   alta resolución, "Flooded Area" (inundación) y "Mudflow" (huaico), y manzanas con grado de daño.
2. GFM 2017: unión de todas las fechas con agua anómala entre dic-2016 y may-2017 (radar, 20 m).
3. GFM 2023: lo mismo entre ene-2023 y jun-2023. En 2023 no hubo activación de Copernicus EMS.

Un edificio cuenta como afectado si su centroide cae dentro de la zona. Los edificios de Microsoft
vienen de imágenes de varios años (posteriores a 2017 en su mayoría): en 2017 puede haber casas que
aún no existían, y eso se declara como limitación.

Escribe en datos/procesados/:
- edificios_{zona}.csv: conteos por fuente y categoría.
- web: ../web/data/edificios_{zona}.geojson (edificios afectados en algún evento + contexto cercano)
  y ../web/data/zonas_{zona}.geojson (polígonos de inundación y huaico de cada fuente).
"""
import os

os.environ.update(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",
                  GDAL_HTTP_MULTIPLEX="YES", GDAL_HTTP_VERSION="2",
                  GDAL_HTTP_MERGE_CONSECUTIVE_RANGES="YES", VSI_CACHE="TRUE",
                  GDAL_HTTP_MAX_RETRY="4", GDAL_HTTP_RETRY_DELAY="3")

import glob
import warnings
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import shapes
from rasterio.warp import transform_bounds
from rasterio.windows import from_bounds
from shapely.geometry import box, shape

warnings.filterwarnings("ignore", category=RuntimeWarning)
BASE = Path(__file__).resolve().parent.parent
ORIG = BASE / "datos" / "originales"
PROC = BASE / "datos" / "procesados"
WEB = BASE / "web" / "data"
CRS_METROS = "EPSG:32717"  # UTM 17S: Piura y Trujillo
ZONAS = {"piura": (-80.80, -5.45, -80.58, -5.12), "trujillo": (-79.14, -8.16, -78.98, -8.02)}
DANADO = ["Negligible to slight damage", "Moderately Damaged", "Highly Damaged", "Completely Destroyed"]
GRADO_ES = {"Negligible to slight damage": "leve", "Moderately Damaged": "moderado",
            "Highly Damaged": "grave", "Completely Destroyed": "destruido"}


def capas_ems(caja):
    """Polígonos de inundación/huaico y manzanas con daño de Copernicus EMS 2017 dentro de la caja."""
    crisis, manzanas = [], []
    for zp in sorted(glob.glob(str(ORIG / "copernicus_ems_2017" / "*.zip"))):
        if "REFERENCE" in zp:
            continue
        for capa in zipfile.ZipFile(zp).namelist():
            if capa.endswith(("crisis_information_poly.shp", "crisis_information_poly_grading.shp")):
                g = gpd.read_file(f"zip://{zp}!{capa}").to_crs(4326)
                crisis.append(g[g.intersects(caja)][["interpret", "src_date", "geometry"]])
            elif capa.endswith("settlements_poly_grading.shp"):
                g = gpd.read_file(f"zip://{zp}!{capa}").to_crs(4326)
                manzanas.append(g[g.intersects(caja)][["grading", "geometry"]])
    crisis = pd.concat(crisis, ignore_index=True)
    crisis["tipo"] = crisis["interpret"].map({"Flooded Area": "inundacion", "Mudflow": "huaico"})
    crisis = crisis.dropna(subset=["tipo"]).dissolve(by="tipo", as_index=False)[["tipo", "geometry"]]
    manzanas = pd.concat(manzanas, ignore_index=True)
    return crisis, manzanas


def gfm_union(evento, caja):
    """Unión de las fechas con inundación GFM (20 m) dentro de la caja: polígonos y n° de fechas."""
    inv = pd.read_csv(PROC / "gfm_inventario.csv")
    inv = inv[inv["evento"] == int(evento)]
    lecturas = []
    for tile, g in inv.groupby("tile"):
        with rasterio.open(g["url_ensemble_flood_extent"].iloc[0]) as ds:
            limites = transform_bounds("EPSG:4326", ds.crs, *caja.bounds)
            o, s, e, n = ds.bounds
            if limites[2] <= o or limites[0] >= e or limites[3] <= s or limites[1] >= n:
                continue
            ventana = from_bounds(*limites, transform=ds.transform).round_offsets().round_lengths()
            lecturas.append((tile, list(g["url_ensemble_flood_extent"]), ds.crs, ventana,
                             ds.window_transform(ventana)))

    poligonos = []
    for tile, urls, crs, ventana, transform in lecturas:
        def leer(url):
            with rasterio.open(url) as ds:
                return ds.read(1, window=ventana, boundless=True, fill_value=255)
        with ThreadPoolExecutor(6) as pool:
            capas = list(pool.map(leer, urls))
        frecuencia = np.sum([c == 1 for c in capas], axis=0).astype("uint8")
        for geom, valor in shapes(frecuencia, mask=frecuencia > 0, transform=transform):
            poligonos.append({"geometry": shape(geom), "fechas_inundado": int(valor)})
        print(f"  GFM {evento} {tile}: {len(urls)} escenas leídas")
    if not poligonos:
        return gpd.GeoDataFrame({"fechas_inundado": []}, geometry=[], crs="EPSG:4326")
    return gpd.GeoDataFrame(poligonos, crs=lecturas[0][2]).to_crs(4326)


def main():
    WEB.mkdir(parents=True, exist_ok=True)
    for zona, limites in ZONAS.items():
        print(f"== {zona}")
        caja = box(*limites)
        edif = gpd.read_file(ORIG / "edificios_microsoft" / f"{zona}.gpkg")
        edif = edif[edif.intersects(caja)].reset_index(drop=True)
        centros = gpd.GeoDataFrame(geometry=edif.to_crs(CRS_METROS).centroid.to_crs(4326))

        crisis, manzanas = capas_ems(caja)
        gfm = {ev: gfm_union(ev, caja) for ev in ("2017", "2023")}

        for tipo in ("inundacion", "huaico"):
            zona_tipo = crisis[crisis["tipo"] == tipo]
            edif[f"ems2017_{tipo}"] = (centros.within(zona_tipo.union_all()) if len(zona_tipo)
                                       else False)
        unido = gpd.sjoin(centros, manzanas, how="left", predicate="within")
        grado = unido[~unido.index.duplicated()]["grading"]
        edif["ems2017_grado"] = grado.where(grado.isin(DANADO)).map(GRADO_ES)
        for ev, g in gfm.items():
            edif[f"gfm{ev}"] = centros.within(g.union_all()) if len(g) else False

        edif["afectado_2017"] = edif[["ems2017_inundacion", "ems2017_huaico", "gfm2017"]].any(axis=1) | \
            edif["ems2017_grado"].notna()
        edif["afectado_2023"] = edif["gfm2023"]

        resumen = {
            "zona": zona, "edificios": len(edif),
            "ems2017_inundacion": int(edif["ems2017_inundacion"].sum()),
            "ems2017_huaico": int(edif["ems2017_huaico"].sum()),
            "ems2017_manzana_danada": int(edif["ems2017_grado"].notna().sum()),
            "gfm2017": int(edif["gfm2017"].sum()), "gfm2023": int(edif["gfm2023"].sum()),
            "afectado_2017": int(edif["afectado_2017"].sum()), "afectado_2023": int(edif["afectado_2023"].sum()),
            "afectado_ambos": int((edif["afectado_2017"] & edif["afectado_2023"]).sum()),
            "ems_inundacion_km2": round(crisis.loc[crisis["tipo"] == "inundacion"].to_crs(CRS_METROS).area.sum() / 1e6, 2),
            "gfm2017_km2": round(gfm["2017"].to_crs(CRS_METROS).area.sum() / 1e6, 2),
            "gfm2023_km2": round(gfm["2023"].to_crs(CRS_METROS).area.sum() / 1e6, 2),
        }
        pd.DataFrame([resumen]).to_csv(PROC / f"edificios_{zona}.csv", index=False)
        print(pd.Series(resumen).to_string())

        # Web: edificios afectados en algún evento y, como contexto, los que están a menos de 300 m.
        afectados = edif[edif["afectado_2017"] | edif["afectado_2023"]]
        cerca = afectados.to_crs(CRS_METROS).buffer(300).union_all()
        contexto = edif[edif.to_crs(CRS_METROS).within(cerca)]
        web = contexto[["ems2017_inundacion", "ems2017_huaico", "ems2017_grado", "gfm2017", "gfm2023",
                        "afectado_2017", "afectado_2023", "geometry"]].copy()
        web["ems2017_grado"] = web["ems2017_grado"].fillna("")
        web.to_file(WEB / f"edificios_{zona}.geojson", driver="GeoJSON", COORDINATE_PRECISION=6)

        capas = [crisis.assign(fuente="Copernicus EMS 2017")[["fuente", "tipo", "geometry"]]]
        for ev, g in gfm.items():
            if len(g):
                capas.append(gpd.GeoDataFrame({"fuente": [f"GFM {ev}"], "tipo": ["inundacion"]},
                                              geometry=[g.union_all()], crs=4326))
        zonas_web = pd.concat(capas, ignore_index=True)
        zonas_web["geometry"] = zonas_web.to_crs(CRS_METROS).simplify(8).to_crs(4326)
        zonas_web.to_file(WEB / f"zonas_{zona}.geojson", driver="GeoJSON", COORDINATE_PRECISION=6)
        print(f"  web: {len(web):,} edificios, {len(zonas_web)} capas de zonas")


if __name__ == "__main__":
    main()
