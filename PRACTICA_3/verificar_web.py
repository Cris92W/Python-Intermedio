"""Comprueba las respuestas de preguntas.csv con el buscador web del RCA, sin usar server.py.

    uv run verificar_web.py

Hace las mismas búsquedas que una persona en https://enlinea.senace.gob.pe/Certificacion/CatalagoCertificacion
(por número de trámite, titular, resultado, tipo de estudio, sector o departamento) y cuenta o resta fechas sobre
las filas que devuelve la página. Así la verdad de cada pregunta no depende del código del servidor.
"""
import statistics
import time
from datetime import date, datetime
from html.parser import HTMLParser

import httpx

URL = "https://enlinea.senace.gob.pe/Certificacion/CatalagoCertificacion/BuscarCatalogoCertificacion"
# Los filtros de la página en «todos», con el SENACE como ente evaluador (IdOrigen=1)
BASE = {"NroCatalogo": "", "NroRecurso": "", "DesTitular": "", "NroRuc": "", "IdTipoEstudio": "0",
        "IdEstadoProyecto": "0", "CodSector": "0|0", "IdGrupoSector": "0", "DesConsultora": "", "NroRucCons": "",
        "IdDepartamento": "00", "IdProvincia": "", "IdDistrito": "", "NombreProyecto": "", "IdOrigen": "1",
        "Unidad": "", "IdEntidadOr": "0"}
# Códigos de las listas desplegables de la página
APROBADO, EIA_D, ITS, MINERIA, PIURA = "50", "3", "4", "1|1", "20"


class _Tabla(HTMLParser):
    def __init__(self):
        super().__init__()
        self.filas, self._fila, self._celda = [], None, None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._fila = []
        elif tag in ("td", "th") and self._fila is not None:
            self._celda = []

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._celda is not None:
            self._fila.append(" ".join("".join(self._celda).split()))
            self._celda = None
        elif tag == "tr" and self._fila:
            self.filas.append(self._fila)
            self._fila = None

    def handle_data(self, data):
        if self._celda is not None:
            self._celda.append(data)


def buscar(**filtros):
    """Las filas que muestra la página para esos filtros. Si el SENACE se satura, espera y reintenta."""
    for intento in range(4):
        r = httpx.post(URL, params={**BASE, **filtros}, content=b"",
                       headers={"X-Requested-With": "XMLHttpRequest"}, timeout=180)
        p = _Tabla()
        p.feed(r.text)
        cabecera = next((f for f in p.filas if "NRO. TRÁMITE" in f), None)
        if cabecera:
            time.sleep(1)
            return [dict(zip(cabecera, f)) for f in p.filas if len(f) == len(cabecera) and f[0].isdigit()]
        time.sleep(15)
    raise SystemExit(f"El RCA no respondió a {filtros}")


def fecha(s):
    return datetime.strptime(s, "%d/%m/%Y").date()


def resueltos(filas, desde, hasta):
    return [f for f in filas if desde <= fecha(f["FECHA RESOLUCIÓN"]) <= hasta]


def dias(f):
    return (fecha(f["FECHA RESOLUCIÓN"]) - fecha(f["FECHA INGRESO"])).days


if __name__ == "__main__":
    A2025 = date(2025, 1, 1), date(2025, 12, 31)
    print("total_2025       ", len(resueltos(buscar(), *A2025)))
    aprobados = buscar(IdEstadoProyecto=APROBADO)
    print("aprobados_2025   ", len(resueltos(aprobados, *A2025)))
    print("aprobados_set26  ", len(resueltos(aprobados, date(2026, 9, 1), date(2026, 9, 30))))
    print("eiad_2025        ", len(resueltos(buscar(IdTipoEstudio=EIA_D), *A2025)))
    print("mineria_t3_2026  ", len(resueltos(buscar(IdEstadoProyecto=APROBADO, CodSector=MINERIA),
                                             date(2026, 7, 1), date(2026, 9, 30))))
    # El filtro de departamento de la página no filtra: devuelve todo el periodo. Se cuentan a mano las filas cuya
    # ubicación incluye PIURA (un proyecto lineal puede listar varios departamentos).
    periodo = resueltos(buscar(IdDepartamento=PIURA), date(2026, 1, 1), date(2026, 9, 30))
    print("piura_2026       ", sum("PIURA-" in f["UBIGEO"] for f in periodo),
          f"(la página devuelve {len(periodo)} filas con el filtro de Piura)")
    f = buscar(NroRecurso="03951-2025")[0]
    print("dias_iscaycruz   ", dias(f), f"({f['FECHA INGRESO']} → {f['FECHA RESOLUCIÓN']})")
    f = next(x for x in buscar(DesTitular="LAS BAMBAS") if x["FECHA RESOLUCIÓN"].endswith("/09/2026"))
    print("rd_las_bambas    ", f["NRO. RESOLUCIÓN"])
    f = next(x for x in buscar(DesTitular="QUELLAVECO") if x["FECHA RESOLUCIÓN"].endswith("/08/2026"))
    print("dias_quellaveco  ", dias(f), f"({f['NRO. TRÁMITE']}: {f['FECHA INGRESO']} → {f['FECHA RESOLUCIÓN']})")
    plazos = [dias(x) for x in resueltos(buscar(IdTipoEstudio=ITS), *A2025)]
    print("mediana_its_2025 ", statistics.median(p for p in plazos if p >= 0), f"({len(plazos)} ITS)")
