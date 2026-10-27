"""Huaicos en Piura: inventario de INGEMMET y eventos documentados de 2017 y 2023.

    .venv/Scripts/python.exe scripts/obtener_huaicos.py

El radar no ve los huaicos (son angostos, duran horas y bajan por laderas que el radar no observa bien),
así que se usan dos fuentes que no vienen del satélite:

1. Inventario de peligros geológicos de INGEMMET (GEOCATMIN, servicio SERV_PELIGROS_GEOLOGICOS, capa 0):
   puntos levantados en campo, sobre todo entre 2002 y 2010, y algunos de emergencias recientes
   reportadas por el COEN. Se bajan los "flujos" del departamento de Piura (UBIGEO 20...): flujo de
   detritos y flujo de lodo, que es lo que en el Perú se llama huaico, más avalanchas y flujos de tierra.
   Muestran dónde bajan huaicos, no cuándo.
2. datos/procesados/huaicos_eventos.csv: huaicos y activaciones de quebradas de 2017 y 2023 en Piura,
   compilados a mano de INDECI, INGEMMET (informes técnicos y registros del COEN) y prensa, con su fuente.
   Cuando solo se conoce el mes, la columna `fecha` es una fecha de orden y `fecha_texto` dice lo que se sabe.

Escribe datos/procesados/ingemmet_flujos_piura.csv, web/data/huaicos_ingemmet.geojson y
web/data/huaicos_eventos.geojson.
"""
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests
import truststore

# El servidor de INGEMMET no envía el certificado intermedio: se valida con el almacén del sistema operativo,
# que sí lo completa, en lugar de desactivar la verificación.
truststore.inject_into_ssl()

BASE = Path(__file__).resolve().parent.parent
PROC = BASE / "datos" / "procesados"
WEB = BASE / "web" / "data"
SERVICIO = ("https://geocatmin.ingemmet.gob.pe/arcgis/rest/services/"
            "SERV_PELIGROS_GEOLOGICOS/MapServer/0/query")
CABECERAS = {"User-Agent": "tarea3-unmsm (https://github.com/Cris92W/Python-Intermedio)"}
TIPOS = {"1000|1500|1501": "Aluvión", "1000|1500|1502": "Avalancha de detritos",
         "1000|1500|1503": "Avalancha de rocas", "1000|1500|1504": "Flujo de detritos",
         "1000|1500|1505": "Flujo de lodo", "1000|1500|1506": "Flujo de roca",
         "1000|1500|1507": "Flujo de tierra", "1000|1500|1508": "Inundación de detritos"}
HUAICO = ("Flujo de detritos", "Flujo de lodo")


def main():
    params = {"where": "UBIGEO LIKE '20%' AND TIP_PELIGRO='1000|1500' AND REGISTRO='Publicable'",
              "outFields": "COD_INV,UBIGEO,NM_PROV,NM_DIST,NM_SECTOR,FECHA,NOM_PELIGRO,TIESTU_ANO",
              "returnGeometry": "true", "outSR": "4326", "f": "geojson"}
    r = requests.get(SERVICIO, params=params, headers=CABECERAS, timeout=120)
    r.raise_for_status()
    flujos = gpd.GeoDataFrame.from_features(r.json()["features"], crs=4326)
    flujos["tipo"] = flujos["NOM_PELIGRO"].map(TIPOS)
    flujos["huaico"] = flujos["tipo"].isin(HUAICO)
    flujos["anio"] = pd.to_datetime(flujos["FECHA"], unit="ms").dt.year.astype("Int64")
    flujos["provincia"] = flujos["NM_PROV"].str.upper().str.replace("MORROPON", "MORROPÓN")
    flujos = flujos.rename(columns={"NM_DIST": "distrito", "NM_SECTOR": "sector", "TIESTU_ANO": "estudio"})
    flujos = flujos.sort_values("COD_INV").reset_index(drop=True)
    flujos.drop(columns="geometry").assign(lon=flujos.geometry.x.round(5), lat=flujos.geometry.y.round(5)) \
        .to_csv(PROC / "ingemmet_flujos_piura.csv", index=False, encoding="utf-8")
    flujos[["tipo", "huaico", "provincia", "distrito", "sector", "anio", "geometry"]].to_file(
        WEB / "huaicos_ingemmet.geojson", driver="GeoJSON", COORDINATE_PRECISION=5)

    eventos = pd.read_csv(PROC / "huaicos_eventos.csv", dtype={"evento": str})
    eventos = gpd.GeoDataFrame(eventos, geometry=gpd.points_from_xy(eventos["lon"], eventos["lat"]), crs=4326)
    eventos.drop(columns=["lon", "lat"]).to_file(WEB / "huaicos_eventos.geojson", driver="GeoJSON",
                                                 COORDINATE_PRECISION=5)

    print(f"INGEMMET: {len(flujos)} flujos en Piura, {flujos['huaico'].sum()} de detritos o lodo (huaicos)")
    print(flujos.groupby(["provincia", "tipo"]).size().unstack(fill_value=0).to_string())
    print(flujos["anio"].value_counts(dropna=False).sort_index().to_string())
    print(f"\nEventos documentados: {len(eventos)}")
    print(eventos[["evento", "fecha_texto", "distrito", "lugar", "tipo"]].to_string(index=False))


if __name__ == "__main__":
    main()
