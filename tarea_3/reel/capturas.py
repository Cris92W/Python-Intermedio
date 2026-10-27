"""Capturas verticales del dashboard publicado para la escena final del reel (Chrome sin interfaz por CDP).

Uso (desde tarea_3/reel):  ../.venv/Scripts/python capturas.py
Escribe recursos/dash_*.png de 1080 × 1920 (pantalla de celular de 540 × 960 a doble densidad).
"""
import base64
import json
import shutil
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

import websocket

AQUI = Path(__file__).resolve().parent
URL = "https://cris92w.github.io/Python-Intermedio/tarea_3/web/"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
# (nombre, JavaScript que deja la página en la vista, espera en s)
VISTAS = [
    ("portada", "scrollTo(0, 0)", 2),
    ("agua", "(() => { const s = document.querySelectorAll('#stA-sec .step')[4]; scrollTo(0, s.getBoundingClientRect().top + scrollY - innerHeight * .35); })()", 6),
    ("explorar", "document.querySelector('#cap6 .mapgrid').scrollIntoView({block: 'start'})", 6),
    ("metodo", "document.querySelector('.flujo').scrollIntoView({block: 'start'})", 3),
]


def main():
    perfil = tempfile.mkdtemp()
    proc = subprocess.Popen([CHROME, "--headless=new", "--remote-debugging-port=9336", f"--user-data-dir={perfil}",
                             "--enable-unsafe-swiftshader", "--use-angle=swiftshader", "--hide-scrollbars", "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                pest = json.load(urllib.request.urlopen("http://127.0.0.1:9336/json"))
                break
            except Exception:
                time.sleep(0.3)
        ws = websocket.create_connection([p for p in pest if p["type"] == "page"][0]["webSocketDebuggerUrl"],
                                         timeout=90, suppress_origin=True)
        n = [0]

        def cmd(metodo, **params):
            n[0] += 1
            ws.send(json.dumps({"id": n[0], "method": metodo, "params": params}))
            while True:
                m = json.loads(ws.recv())
                if m.get("id") == n[0]:
                    return m.get("result", {})

        cmd("Page.enable")
        cmd("Emulation.setDeviceMetricsOverride", width=540, height=960, deviceScaleFactor=2, mobile=True)
        cmd("Page.navigate", url=URL)
        time.sleep(12)
        for nombre, js, espera in VISTAS:
            cmd("Runtime.evaluate", expression=js)
            time.sleep(espera)
            img = cmd("Page.captureScreenshot", format="png")
            (AQUI / "recursos" / f"dash_{nombre}.png").write_bytes(base64.b64decode(img["data"]))
            print("captura", nombre)
    finally:
        proc.kill()
        time.sleep(1)
        shutil.rmtree(perfil, ignore_errors=True)


if __name__ == "__main__":
    main()
