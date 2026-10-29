"""El contrato del servidor, adaptado del BCRP al SENACE: si estas pruebas pasan, Claude Code y evaluar.py pueden usarlo.

    uv run pytest -q

Llaman al servidor en memoria, igual que lo haría Claude Code, y piden datos reales al RCA del SENACE. Las cifras
esperadas son de periodos cerrados (2025, setiembre de 2026), que ya no cambian aunque el registro siga creciendo.
"""
import asyncio

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from server import mcp


async def _con_cliente(f):
    async with Client(mcp) as c:
        return await f(c)


def llamar(herramienta, **args):
    return asyncio.run(_con_cliente(lambda c: c.call_tool(herramienta, args))).data


def test_buscar_encuentra_las_bambas():
    r = llamar("buscar_certificaciones", texto="las bambas", desde="2025", hasta="2025")
    assert "M-ITS-00018-2025" in [x["tramite"] for x in r["tramites"]]
    assert all("BAMBAS" in x["titular"] for x in r["tramites"])
    assert {"tramite", "titular", "tipo", "resultado", "resolucion", "fecha_resolucion"} <= r["tramites"][0].keys()


def test_cuatro_herramientas_como_minimo():
    nombres = {t.name for t in asyncio.run(_con_cliente(lambda c: c.list_tools()))}
    assert {"buscar_certificaciones", "certificacion", "resumen"} <= nombres
    assert len(nombres) >= 4, "falta la herramienta propia"


def test_ficha_de_un_tramite():
    r = llamar("certificacion", tramite="03951-2025")
    assert r["titular"] == "EMPRESA MINERA LOS QUENUALES S.A.C."
    assert "00166-2026" in r["resolucion"]
    assert (r["fecha_ingreso"], r["fecha_resolucion"], r["dias_de_evaluacion"]) == ("2025-09-19", "2026-10-23", 399)
    assert r["fuente"].startswith("https://enlinea.senace.gob.pe")


def test_resumen_de_un_anio():
    r = llamar("resumen", desde="2025", hasta="2025")
    assert r["total"] == 212
    assert r["por_resultado"]["APROBADO"] == 131 and r["por_resultado"]["CONFORME"] == 70
    assert len(r["por_mes"]) == 12 and sum(r["por_mes"].values()) == 212


def test_resumen_con_filtros_y_siglas():
    r = llamar("resumen", desde="2026-09", hasta="2026-09", resultado="aprobado")
    assert r["total"] == 14
    assert r["por_sector"]["MINERIA"] == 8
    assert r["primero"]["tramite"] == "M-ITS-00102-2026"
    its = llamar("resumen", desde="2026-09", hasta="2026-09", resultado="aprobado", tipo="ITS")
    assert its["total"] == 12


def test_errores_claros():
    with pytest.raises(ToolError, match="XX-999"):
        llamar("certificacion", tramite="XX-999")
    with pytest.raises(ToolError, match="MINERIA"):   # un sector mal escrito lista los válidos
        llamar("resumen", desde="2025", hasta="2025", sector="pesca")


def test_herramienta_propia_plazos():
    r = llamar("plazos", desde="2025", hasta="2025", tipo="EIA-d")
    assert r["tramites"] == 6
    assert r["dias_mediana"] == 498
    assert r["mas_lento"]["tramite"] == "M-EIAD-00156-2022" and r["mas_lento"]["dias"] == 1013


def test_un_recurso():
    async def contar(c):
        return len(await c.list_resources()) + len(await c.list_resource_templates())
    assert asyncio.run(_con_cliente(contar)) >= 1


def test_un_prompt():
    assert len(asyncio.run(_con_cliente(lambda c: c.list_prompts()))) >= 1
