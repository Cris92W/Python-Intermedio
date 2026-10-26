"""Dashboard de la Tarea 2: documentos y entrevistas peruanos convertidos en texto buscable.

La app no corre modelos: solo lee los CSV que prepararon los notebooks (datos/) y los ejemplos que se
pueden publicar (datos/ejemplos/). Todos los textos están seudonimizados.

Ejecutar en local (desde tarea_2):  streamlit run app.py
"""
import html
import json
import re
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

BASE = Path(__file__).resolve().parent
DATOS = BASE / "datos"
EJEMPLOS = DATOS / "ejemplos"
TIPOS_DOC = ["impreso", "foto", "manuscrito"]
MODELOS = ["PaddleOCR (base)", "EasyOCR", "faster-whisper small (base)", "Qwen3-ASR 0.6B"]
# Medido en 02_evaluacion.ipynb (pesos de cada modelo en disco)
DISCO_MB = {"PaddleOCR (base)": 146, "EasyOCR": 94, "faster-whisper small (base)": 464, "Qwen3-ASR 0.6B": 1503}
COLORES = {"PaddleOCR (base)": "#2a6fdb", "EasyOCR": "#e8833a", "faster-whisper small (base)": "#2a6fdb",
           "Qwen3-ASR 0.6B": "#e8833a"}

st.set_page_config(page_title="Voces y documentos peruanos", page_icon="📜", layout="wide")


# ─────────────────────────────────────────────────────────────── datos
@st.cache_data
def cargar_datos():
    fuentes = pd.read_csv(DATOS / "fuentes.csv").set_index("id")
    docs = pd.read_csv(DATOS / "documentos.csv")
    clips = pd.read_csv(DATOS / "transcripciones.csv")
    for df in (docs, clips):
        for col in ["repositorio", "fuente_url", "licencia", "licencia_url", "autor", "descripcion", "fecha_descarga"]:
            df[col] = df["id"].map(fuentes[col])
    docs["imagen_publicable"] = docs["id"].map(lambda i: (EJEMPLOS / "documentos" / f"{i}.jpg").exists())
    clips["audio_publicable"] = clips["id"].map(lambda i: (EJEMPLOS / "audio" / f"{i}.wav").exists())
    clips["minutos"] = clips["duracion_seg"] / 60

    llm = pd.read_csv(DATOS / "extraccion_llm.csv")
    llm["campos"] = llm["campos_json"].map(lambda s: json.loads(s) if isinstance(s, str) else None)
    evaluacion = pd.read_csv(DATOS / "evaluacion_modelos.csv")
    auditoria = pd.read_csv(DATOS / "auditoria_llm.csv")
    auditoria["correcto"] = auditoria["veredicto"].str.strip().str.lower().isin(["sí", "si"])
    return fuentes.reset_index(), docs, clips, llm, evaluacion, auditoria


def tasa_global(df):
    """Errores totales entre unidades totales (caracteres o palabras de la referencia)."""
    return df["errores"].sum() / df["unidades"].sum() if len(df) else float("nan")


def contiene(serie, consulta):
    if not consulta:
        return pd.Series(True, index=serie.index)
    return serie.fillna("").str.contains(re.escape(consulta), case=False)


def resaltar(texto, consulta):
    """Texto escapado en HTML, con la búsqueda marcada."""
    seguro = html.escape(texto)
    if consulta:
        seguro = re.sub(re.escape(html.escape(consulta)), lambda m: f"<mark>{m.group(0)}</mark>", seguro, flags=re.I)
    return seguro


def caja(contenido_html, alto=360):
    st.markdown(f"<div style='white-space:pre-wrap; max-height:{alto}px; overflow-y:auto; padding:.75rem 1rem; "
                f"border:1px solid rgba(128,128,128,.35); border-radius:.5rem; font-size:.92rem; line-height:1.5'>"
                f"{contenido_html}</div>", unsafe_allow_html=True)


def turnos_html(texto, consulta):
    """Separa la transcripción por las marcas [HABLANTE_N] en un renglón por turno."""
    partes = re.split(r"\[HABLANTE_(\d+)\]", texto)
    renglones = [resaltar(partes[0].strip(), consulta)] if partes[0].strip() else []
    for n, frase in zip(partes[1::2], partes[2::2]):
        renglones.append(f"<b>Hablante {n}:</b> {resaltar(frase.strip(), consulta)}")
    return "<br>".join(renglones)


def descarga(df, nombre, clave):
    st.download_button("⬇️ Descargar CSV", df.to_csv(index=False).encode("utf-8"), file_name=nombre,
                       mime="text/csv", key=clave)


def atribucion(fila):
    return (f"Fuente: [{fila['repositorio']}]({fila['fuente_url']}) · Licencia: [{fila['licencia']}]({fila['licencia_url']}) "
            f"· Autor: {fila['autor']} · Descargado el {fila['fecha_descarga']}")


def mostrar_campos_llm(llm, id_):
    fila = llm[llm["id"] == id_]
    if fila.empty:
        return
    fila = fila.iloc[0]
    if not fila["json_valido"]:
        st.warning("El LLM no devolvió un JSON válido para este registro (la respuesta se repetía hasta cortarse).")
        return
    campos = pd.DataFrame([{"campo": k, "valor": " · ".join(map(str, v)) if isinstance(v, list) else ("null" if v is None else str(v))}
                           for k, v in fila["campos"].items()])
    st.dataframe(campos, hide_index=True)
    st.caption(f"Modelo: {fila['modelo_llm']}")


def mostrar_auditoria(auditoria, id_):
    a = auditoria[auditoria["id"] == id_]
    if a.empty:
        return
    completa = a["correcto"].all()
    st.markdown(f"**Auditoría humana:** {a['correcto'].sum()} de {len(a)} campos correctos — "
                f"extracción {'completamente correcta ✅' if completa else 'con errores ❌'}")
    st.dataframe(a[["campo", "valor_llm", "veredicto", "comentario"]], hide_index=True)


fuentes, docs, clips, llm, evaluacion, auditoria = cargar_datos()

# ─────────────────────────────────────────────────────────────── filtros
with st.sidebar:
    st.header("Filtros")
    consulta = st.text_input("🔎 Buscar en los textos OCR y ASR", placeholder="por ejemplo: ceviche, Perú, coca").strip()
    tipos = st.multiselect("Tipo de documento", TIPOS_DOC, default=TIPOS_DOC)
    fuentes_audio = sorted(clips["fuente"].unique())
    fuentes_sel = st.multiselect("Fuente del audio", fuentes_audio, default=fuentes_audio)
    dur_max = int(clips["duracion_seg"].max()) + 1
    rango = st.slider("Duración del clip (s)", 0, dur_max, (0, dur_max))
    modelos = st.multiselect("Modelos evaluados", MODELOS, default=MODELOS)
    st.caption("Los filtros actualizan los gráficos, las tablas y los exploradores de cada pestaña.")

docs_f = docs[docs["tipo"].isin(tipos) & contiene(docs["texto_ocr"], consulta)]
clips_f = clips[clips["fuente"].isin(fuentes_sel) & clips["duracion_seg"].between(*rango)
                & contiene(clips["texto_asr"], consulta)]
eval_f = evaluacion[evaluacion["modelo"].isin(modelos)
                    & evaluacion["id"].isin(set(docs_f["id"]) | set(clips_f["id"]))]

# ─────────────────────────────────────────────────────────────── encabezado
st.title("📜 Voces y documentos peruanos: del archivo escaneado al texto buscable")
st.markdown("**Pregunta:** ¿se pueden convertir documentos escaneados y entrevistas en audio en un archivo de texto "
            "estructurado y buscable?")
st.markdown(
    "**Método.** 25 documentos (impresos, fotos y manuscritos) y 28 clips de audio en español peruano, de Wikimedia "
    "Commons, archive.org y OpenSLR 73, se leyeron con **PaddleOCR** y se transcribieron con **faster-whisper `small`** "
    "y diarización. Los nombres de personas se reemplazaron por `[PERSONA_NN]`. Un LLM local (**Qwen3-0.6B**) extrajo "
    "campos JSON de cada texto. En una muestra de 10 documentos y 10 clips transcritos a mano se midieron CER y WER "
    "frente a **EasyOCR** y **Qwen3-ASR**, y una persona auditó 20 extracciones del LLM. Todo se calculó en los "
    "notebooks; esta app solo explora los resultados.")

ocr = {m: tasa_global(evaluacion[evaluacion["modelo"] == m]) for m in MODELOS}
por_extraccion = auditoria.groupby("id")["correcto"].all()
acuerdo = int(por_extraccion.sum())
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Documentos procesados", len(docs), help="8 impresos, 8 fotos y 9 manuscritos")
c2.metric("Minutos de audio transcritos", f"{clips['minutos'].sum():.1f}", help=f"{len(clips)} clips")
c3.metric("CER PaddleOCR (base)", f"{ocr['PaddleOCR (base)']:.3f}",
          delta=f"{ocr['PaddleOCR (base)'] - ocr['EasyOCR']:+.3f} frente a EasyOCR", delta_color="inverse",
          help="Errores por carácter en los 10 documentos de la muestra. EasyOCR: " f"{ocr['EasyOCR']:.3f}")
c4.metric("WER faster-whisper (base)", f"{ocr['faster-whisper small (base)']:.3f}",
          delta=f"{ocr['faster-whisper small (base)'] - ocr['Qwen3-ASR 0.6B']:+.3f} frente a Qwen3-ASR", delta_color="inverse",
          help="Errores por palabra en los 10 clips de la muestra. Qwen3-ASR: " f"{ocr['Qwen3-ASR 0.6B']:.3f}")
c5.metric("Acuerdo LLM-humano", f"{acuerdo}/20 ({acuerdo / 20:.0%})",
          help=f"Extracciones con todos sus campos correctos. Campos correctos: {auditoria['correcto'].sum()} de {len(auditoria)}")

if consulta:
    st.info(f"Búsqueda «{consulta}»: {len(docs_f)} documentos y {len(clips_f)} clips la contienen.")

tab_res, tab_doc, tab_aud, tab_llm, tab_fuentes = st.tabs(
    ["📊 Resultados", "📄 Documentos", "🎙️ Audios", "🤖 Extracción con LLM", "ℹ️ Fuentes y método"])

# ─────────────────────────────────────────────────────────────── resultados
with tab_res:
    st.subheader("CER y WER en la muestra de evaluación (10 documentos y 10 clips)")
    st.caption("Las referencias se transcribieron a mano. Referencias y salidas pasan por la misma normalización "
               "(minúsculas, sin puntuación, sin marcas de hablante ni muletillas). Más bajo es mejor.")
    if eval_f.empty:
        st.warning("Ningún archivo de la muestra coincide con los filtros.")
    else:
        filas = []
        for (modalidad, modelo), g in eval_f.groupby(["modalidad", "modelo"], sort=False):
            filas.append({"modalidad": modalidad, "modelo": modelo, "métrica": g["metrica"].iloc[0],
                          "global": round(tasa_global(g), 3), "media por archivo": round(g["valor"].mean(), 3),
                          "archivos": len(g),
                          "latencia": (f"{g['segundos'].mean():.0f} s por documento" if modalidad == "documento"
                                       else f"factor de tiempo real {g['segundos'].sum() / g['duracion_seg'].sum():.2f}"),
                          "disco (MB)": DISCO_MB[modelo]})
        comparativa = pd.DataFrame(filas)
        col_a, col_b = st.columns(2)
        for col, modalidad, metrica in [(col_a, "documento", "CER"), (col_b, "audio", "WER")]:
            datos = eval_f[eval_f["modalidad"] == modalidad]
            if datos.empty:
                col.info(f"Sin archivos de {modalidad} con estos filtros.")
                continue
            globales = {m: tasa_global(g) for m, g in datos.groupby("modelo")}
            mejor = min(globales, key=globales.get)
            unidad = "documentos" if modalidad == "documento" else "clips"
            fig = px.bar(datos, x="id", y="valor", color="modelo", barmode="group", color_discrete_map=COLORES,
                         hover_data={"tipo": True, "errores": True, "unidades": True},
                         labels={"valor": metrica, "id": "", "modelo": "Modelo"},
                         title=(f"{mejor} comete menos errores en los {datos['id'].nunique()} {unidad} filtrados<br>"
                                + " · ".join(f"{metrica} global {m}: {v:.3f}" for m, v in globales.items())))
            fig.update_layout(legend=dict(orientation="h", y=-0.25), margin=dict(t=60))
            col.plotly_chart(fig, key=f"barras_{modalidad}")
        st.markdown("**Tabla comparativa** (sobre los archivos filtrados)")
        st.dataframe(comparativa, hide_index=True)
        st.markdown(
            "**Decisión para un entorno real sin GPU:** PaddleOCR (3,3 veces menos errores que EasyOCR) y "
            "faster-whisper `small` (4,3 veces menos errores que Qwen3-ASR, casi el doble de rápido). "
            "El LLM pequeño solo sirve como borrador con revisión humana.")
        with st.expander("Ver los resultados por archivo"):
            tabla = eval_f[["id", "modalidad", "tipo", "modelo", "metrica", "valor", "errores", "unidades", "segundos"]]
            st.dataframe(tabla, hide_index=True)
            descarga(eval_f, "evaluacion_modelos_filtrada.csv", "dl_eval")

# ─────────────────────────────────────────────────────────────── documentos
with tab_doc:
    st.subheader("Documentos")
    m1, m2, m3 = st.columns(3)
    m1.metric("Documentos que coinciden", f"{len(docs_f)} de {len(docs)}")
    m2.metric("Caracteres leídos", f"{docs_f['caracteres'].sum():,}".replace(",", " "))
    m3.metric("Confianza media del OCR", f"{docs_f['confianza_media'].mean():.3f}" if len(docs_f) else "–")

    if docs_f.empty:
        st.warning("Ningún documento coincide con los filtros.")
    else:
        fig = px.scatter(docs_f, x="caracteres", y="confianza_media", color="tipo", log_x=True, hover_name="id",
                         hover_data={"descripcion": True}, category_orders={"tipo": TIPOS_DOC},
                         labels={"caracteres": "Caracteres leídos (escala log)", "confianza_media": "Confianza media del OCR",
                                 "tipo": "Tipo"},
                         title="Los manuscritos y las fotos tienen textos más cortos y menos confianza del OCR que los impresos")
        fig.update_traces(marker_size=11)
        st.plotly_chart(fig, key="dispersion_docs")

        tabla = docs_f[["id", "tipo", "descripcion", "licencia", "caracteres", "confianza_media", "texto_ocr"]]
        st.dataframe(tabla, hide_index=True, column_config={"texto_ocr": st.column_config.TextColumn("texto OCR", width="large")})
        descarga(tabla, "documentos_filtrados.csv", "dl_docs")

        st.divider()
        st.subheader("Explorador de documentos")
        ids = list(docs_f["id"])
        id_doc = st.selectbox("Elige un documento", ids,
                              format_func=lambda i: f"{i} · {docs.set_index('id').loc[i, 'tipo']} · "
                                                    f"{docs.set_index('id').loc[i, 'descripcion'][:70]}")
        d = docs.set_index("id").loc[id_doc]
        st.markdown(atribucion(d))
        izq, der = st.columns([2, 3])
        with izq:
            if d["imagen_publicable"]:
                st.image(str(EJEMPLOS / "documentos" / f"{id_doc}.jpg"),
                         caption=f"{id_doc} · {d['licencia']} · {d['autor']} (vista reducida)")
            else:
                st.info("La imagen no se muestra porque contiene nombres de personas. El texto y los metadatos "
                        "siguen disponibles, ya seudonimizados.")
        with der:
            st.markdown(f"**Texto OCR** ({d['modelo_ocr'].split(' (')[0]}, {d['caracteres']} caracteres, "
                        f"confianza {d['confianza_media']:.3f})")
            caja(resaltar(d["texto_ocr"], consulta))
            st.markdown("**Campos extraídos por el LLM**")
            mostrar_campos_llm(llm, id_doc)

        e = evaluacion[evaluacion["id"] == id_doc]
        if not e.empty:
            st.markdown("**Este documento está en la muestra de evaluación**")
            cols = st.columns(len(e) + 1)
            for col, (_, fila) in zip(cols, e.iterrows()):
                col.metric(f"CER {fila['modelo']}", f"{fila['valor']:.3f}")
            with st.expander("Ver la referencia manual y la salida de EasyOCR"):
                r1, r2 = st.columns(2)
                with r1:
                    st.markdown("**Referencia manual** (seudonimizada)")
                    caja(resaltar(d["texto_referencia"], consulta), alto=300)
                with r2:
                    st.markdown("**EasyOCR**")
                    caja(resaltar(e.loc[e["modelo"] == "EasyOCR", "texto_modelo"].iloc[0], consulta), alto=300)
        mostrar_auditoria(auditoria, id_doc)

# ─────────────────────────────────────────────────────────────── audios
with tab_aud:
    st.subheader("Audios")
    m1, m2, m3 = st.columns(3)
    m1.metric("Clips que coinciden", f"{len(clips_f)} de {len(clips)}")
    m2.metric("Minutos", f"{clips_f['minutos'].sum():.1f}")
    m3.metric("Clips con 2 o más hablantes", int((clips_f["n_hablantes"] >= 2).sum()))

    if clips_f.empty:
        st.warning("Ningún clip coincide con los filtros.")
    else:
        fig = px.bar(clips_f.sort_values("duracion_seg", ascending=False), x="id", y="minutos", color="fuente",
                     hover_data={"n_hablantes": True, "descripcion": True},
                     labels={"minutos": "Duración (min)", "id": "", "fuente": "Fuente"},
                     title="Las entrevistas de Commons y Radio Bomba aportan casi todo el audio; las frases de OpenSLR duran segundos")
        st.plotly_chart(fig, key="barras_clips")

        tabla = clips_f[["id", "fuente", "tipo", "descripcion", "licencia", "duracion_seg", "n_hablantes", "palabras", "texto_asr"]]
        st.dataframe(tabla, hide_index=True, column_config={"texto_asr": st.column_config.TextColumn("texto ASR", width="large")})
        descarga(tabla, "transcripciones_filtradas.csv", "dl_clips")

        st.divider()
        st.subheader("Explorador de audios")
        ids = list(clips_f["id"])
        id_clip = st.selectbox("Elige un clip", ids,
                               format_func=lambda i: f"{i} · {clips.set_index('id').loc[i, 'fuente']} · "
                                                     f"{clips.set_index('id').loc[i, 'duracion_seg']:.0f} s · "
                                                     f"{clips.set_index('id').loc[i, 'descripcion'][:60]}")
        c = clips.set_index("id").loc[id_clip]
        st.markdown(atribucion(c))
        a1, a2, a3 = st.columns(3)
        a1.metric("Duración", f"{c['duracion_seg']:.1f} s")
        a2.metric("Hablantes (diarización)", int(c["n_hablantes"]))
        a3.metric("Palabras", int(c["palabras"]))
        if c["audio_publicable"]:
            st.audio(str(EJEMPLOS / "audio" / f"{id_clip}.wav"))
            st.caption("Frase leída por una persona anónima del corpus OpenSLR 73 (CC BY-SA 4.0).")
        else:
            st.info("Este audio no se reproduce aquí: es una entrevista con voces y nombres de personas reales. "
                    "La transcripción está seudonimizada y el archivo original está enlazado arriba, en la fuente.")
        st.markdown(f"**Transcripción** ({c['modelo_asr'].split(' (')[0]}, con marcas de hablante)")
        caja(turnos_html(c["texto_asr"], consulta))
        st.markdown("**Campos extraídos por el LLM**")
        mostrar_campos_llm(llm, id_clip)

        e = evaluacion[evaluacion["id"] == id_clip]
        if not e.empty:
            st.markdown("**Este clip está en la muestra de evaluación: comparación de modelos**")
            cols = st.columns(3)
            with cols[0]:
                st.markdown("**Referencia manual**")
                caja(resaltar(c["texto_referencia"], consulta), alto=300)
            for col, modelo in zip(cols[1:], ["faster-whisper small (base)", "Qwen3-ASR 0.6B"]):
                fila = e[e["modelo"] == modelo].iloc[0]
                with col:
                    st.markdown(f"**{modelo}** · WER {fila['valor']:.3f}")
                    caja(resaltar(re.sub(r"\[HABLANTE_\d+\]\s*", "", fila["texto_modelo"]), consulta), alto=300)
        mostrar_auditoria(auditoria, id_clip)

# ─────────────────────────────────────────────────────────────── LLM
with tab_llm:
    st.subheader("Extracción estructurada con LLM y auditoría humana")
    validos = int(llm["json_valido"].sum())
    l1, l2, l3 = st.columns(3)
    l1.metric("JSON válidos", f"{validos} de {len(llm)}")
    l2.metric("Extracciones completamente correctas", f"{acuerdo} de 20")
    l3.metric("Campos correctos en la auditoría", f"{auditoria['correcto'].mean():.0%}")

    por_campo = (auditoria[auditoria["campo"] != "JSON inválido"].groupby(["modalidad", "campo"])["correcto"]
                 .mean().reset_index(name="acierto"))
    fig = px.bar(por_campo, x="campo", y="acierto", color="modalidad", barmode="group", text_auto=".0%",
                 labels={"acierto": "Campos correctos", "campo": "Campo", "modalidad": "Modalidad"},
                 title="El LLM acierta la modalidad y el tema de los documentos,<br>"
                       "pero falla en el número de hablantes, el resumen de documentos y el monto")
    fig.update_yaxes(tickformat=".0%", range=[0, 1.1])
    st.plotly_chart(fig, key="barras_auditoria")
    st.markdown(
        "- **Errores del LLM:** copia el ejemplo del prompt («S/ 15.00») como monto en 8 documentos, inventa fechas "
        "y a veces resume copiando el texto.\n"
        "- **Errores que vienen de la entrada:** el número de hablantes depende de la diarización, los nombres de "
        "figuras públicas llegan seudonimizados y un OCR ilegible arrastra al LLM.")

    ids_vistos = set(docs_f["id"]) | set(clips_f["id"])
    campos = pd.json_normalize(llm["campos"].map(lambda c: c or {}))
    campos.insert(0, "id", llm["id"])
    campos["json_valido"] = llm["json_valido"]
    for col in campos.columns.drop(["id", "json_valido"]):   # valores mezclados (texto, números, listas): todo a texto
        campos[col] = campos[col].map(lambda v: " · ".join(map(str, v)) if isinstance(v, list)
                                      else "" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v))
    campos = campos[campos["id"].isin(ids_vistos)]
    st.markdown(f"**Extracciones** ({len(campos)} registros con los filtros actuales)")
    st.dataframe(campos, hide_index=True)
    descarga(campos, "extraccion_llm_filtrada.csv", "dl_llm")

    st.markdown("**Auditoría humana** (20 extracciones al azar, semilla 2026)")
    st.dataframe(auditoria[["id", "modalidad", "campo", "valor_llm", "veredicto", "comentario"]], hide_index=True)
    descarga(auditoria, "auditoria_llm.csv", "dl_auditoria")

# ─────────────────────────────────────────────────────────────── fuentes
with tab_fuentes:
    st.subheader("Fuentes, licencias y método")
    st.markdown(
        "- **Documentos:** 25 de Wikimedia Commons (dominio público, CC0, CC BY y CC BY-SA), bajados el 23 de octubre "
        "de 2026. Se descartó uno ilegible.\n"
        "- **Audio:** 28 clips (42,4 min) de Wikimedia Commons, archive.org (Radio Bomba, CC BY-NC-SA) y OpenSLR 73 "
        "(CC BY-SA 4.0), bajados el 22 de octubre de 2026. Se descartó uno sin voz.\n"
        "- **Privacidad:** los nombres de personas (también figuras públicas e históricas) se reemplazaron por "
        "`[PERSONA_NN]` con un diccionario revisado a mano. Solo se muestran las imágenes sin nombres de personas y "
        "los audios de OpenSLR, leídos por hablantes anónimos.\n"
        "- **Limitaciones:** la muestra de evaluación es pequeña (10 archivos por modalidad) y una sola persona hizo la "
        "auditoría. La normalización no convierte cifras en palabras («la 1» cuenta como error frente a «la una»).")
    tabla = fuentes[["id", "modalidad", "tipo", "repositorio", "licencia", "autor", "descripcion", "fecha_descarga",
                     "estado", "fuente_url", "licencia_url"]]
    st.dataframe(tabla, hide_index=True, column_config={
        "fuente_url": st.column_config.LinkColumn("fuente"), "licencia_url": st.column_config.LinkColumn("texto de la licencia")})
    descarga(tabla, "fuentes.csv", "dl_fuentes")
    st.caption("Código y notebooks: carpeta tarea_2 del repositorio. La app solo lee CSV preprocesados.")
