"""La figura del informe: aciertos por modo (resultados.csv) y resoluciones del SENACE por mes (el RCA).

    uv run grafico.py      # escribe grafico.png
"""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from server import AQUI, tabla

SUPERFICIE, TINTA, TINTA_2, REJILLA, SERIE = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df", "#2a78d6"
MODOS = {"memoria": "Sin herramientas", "web": "Con búsqueda web", "mcp": "Con el MCP del SENACE"}
MESES = "ene feb mar abr may jun jul ago set oct nov dic".split()

res = pd.read_csv(AQUI / "resultados.csv")
por_modo = res.groupby("modo").agg(aciertos=("resultado", lambda r: (r == "acierta").sum()),
                                   no_sabe=("resultado", lambda r: (r == "no sabe").sum()),
                                   preguntas=("id", "nunique"), segundos=("segundos", "mean"))
df = tabla()
meses = df[df.fecha >= "2024-01-01"].fecha.dt.to_period("M").value_counts().sort_index()
meses = meses.reindex(pd.period_range("2024-01", df.fecha.max().to_period("M"), freq="M"), fill_value=0)

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "text.color": TINTA, "axes.edgecolor": REJILLA,
                     "axes.labelcolor": TINTA_2, "xtick.color": TINTA_2, "ytick.color": TINTA_2})
fig, (a, b) = plt.subplots(1, 2, figsize=(13, 5.2), dpi=150, gridspec_kw={"width_ratios": [1, 1.35], "wspace": 0.28})
fig.patch.set_facecolor(SUPERFICIE)

# A · Aciertos por modo: una barra por modo, con su lectura escrita al lado (el 0 no se ve como barra)
orden = [m for m in MODOS if m in por_modo.index]
y = range(len(orden))[::-1]
a.barh(list(y), [por_modo.aciertos[m] for m in orden], height=0.5, color=SERIE)
for yi, m in zip(y, orden):
    aciertos, no_sabe, n = (int(por_modo.loc[m, c]) for c in ("aciertos", "no_sabe", "preguntas"))
    texto = f"{aciertos} de {n}" + (f" · {no_sabe} veces «no sé»" if no_sabe else "")
    a.text(aciertos + 0.25, yi + 0.05, texto, va="center", fontsize=10.5, fontweight="bold", color=TINTA)
    segundos = f"{por_modo.loc[m, 'segundos']:.1f}".replace(".", ",")
    a.text(aciertos + 0.25, yi - 0.24, f"{segundos} s por pregunta", va="center", fontsize=9, color=TINTA_2)
a.set_yticks(list(y), [MODOS[m] for m in orden], fontsize=10.5, color=TINTA)
a.set_xlim(0, 16)
a.set_xticks(range(0, 11, 2))
a.set_xlabel("Cifras acertadas (de 10)")
a.set_title("¿Cuántas cifras del SENACE acertó Claude?", loc="left", fontsize=12.5, fontweight="bold", pad=24)
a.text(0, 1.03, "Haiku, 10 preguntas con la cifra verificada en la web del RCA", transform=a.transAxes,
       fontsize=9.5, color=TINTA_2)

# B · Resoluciones por mes: el registro que lee el MCP crece cada mes
x = range(len(meses))
b.bar(list(x), meses.values, width=0.78, color=SERIE)
etiquetas = [f"{MESES[p.month - 1]}\n{p.year}" if p.month in (1, 7) else "" for p in meses.index]
b.set_xticks(list(x), etiquetas, fontsize=9)
b.set_xlim(-0.8, len(meses) - 0.2)
b.set_ylabel("Trámites resueltos")
ultimo = meses.index[-1]
b.set_ylim(0, meses.max() * 1.22)
b.annotate(f"{MESES[ultimo.month - 1]} {ultimo.year}: mes en curso,\nhasta el {df.fecha.max().day}",
           xy=(len(meses) - 1, meses.iloc[-1] + 0.3), xytext=(len(meses) - 1, meses.max() * 1.1), ha="right",
           fontsize=9, color=TINTA_2, arrowprops={"arrowstyle": "-", "color": TINTA_2, "lw": 0.8, "relpos": (1, 0), "shrinkA": 2})
b.set_title("Resoluciones del SENACE por mes", loc="left", fontsize=12.5, fontweight="bold", pad=24)
b.text(0, 1.03, f"Registro Administrativo de Certificaciones Ambientales, cualquier resultado; última resolución: {df.fecha.max():%d/%m/%Y}",
       transform=b.transAxes, fontsize=9.5, color=TINTA_2)

for ax in (a, b):
    ax.set_facecolor(SUPERFICIE)
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(length=0)
    ax.grid(axis="x" if ax is a else "y", color=REJILLA, lw=0.8)
    ax.set_axisbelow(True)

fig.text(0.01, 0.01, "Fuente: SENACE, RCA (enlinea.senace.gob.pe); resultados.csv de evaluar.py. Elaboración propia.",
         fontsize=8.5, color=TINTA_2)
fig.savefig(AQUI / "grafico.png", facecolor=SUPERFICIE, bbox_inches="tight", pad_inches=0.25)
print("grafico.png:", dict(por_modo.aciertos), "| meses:", len(meses))
