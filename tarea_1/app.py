"""Tarea 1 – Parte 3: dashboard del clasificador de titulares de El Comercio.

Ejecutar desde la carpeta tarea_1/:   streamlit run app.py
"""
import json
import os
import time
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
# Descarga por HTTP normal: con el cliente xet la descarga de los pesos se quedó colgada en las pruebas
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")

BASE = Path(__file__).resolve().parent
DATOS, MODELO = BASE / "datos", BASE / "modelo"
# Los pesos del modelo (541 MB) no van a GitHub. Si no están en modelo/, se descargan del
# repositorio de Hugging Face indicado en la variable de entorno (o secret de Streamlit) MODELO_HF.
MODELO_HF = os.environ.get("MODELO_HF", "").strip()
MODELO_EMB = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"   # el mismo de la Parte 1
REPO = "https://github.com/Cris92W/Python-Intermedio"

# Nombre visible y color fijo de cada categoría: el color sigue a la categoría en todos los gráficos
CATEGORIAS = {
    "politica": ("Política", "#2a78d6"),
    "economia": ("Economía", "#eb6834"),
    "deportes": ("Deportes", "#1baf7a"),
    "ciencia_tecnologia": ("Ciencia y tecnología", "#eda100"),
}
ETIQUETAS = list(CATEGORIAS)
NOMBRE = {k: v[0] for k, v in CATEGORIAS.items()}
COLOR = {k: v[1] for k, v in CATEGORIAS.items()}
ACENTO = "#6250d6"   # gráficos de una sola serie que no representan una categoría
TIPOS_NER = {"PER": "Personas", "ORG": "Organizaciones", "LOC": "Lugares", "MISC": "Otros"}

# Titulares inventados (no están en el dataset) para probar el clasificador con un clic
EJEMPLOS = {
    "Política": "Congreso aprueba moción de censura contra el ministro del Interior por la ola de extorsiones",
    "Economía": "BCR recorta su tasa de referencia y el dólar cae a su menor nivel en lo que va del año",
    "Deportes": "Alianza Lima vence 2-0 a Cienciano en Matute y se acerca al título del Torneo Clausura",
    "Ciencia y tecnología": "Investigadores peruanos crean una app con inteligencia artificial que detecta el dengue",
    "Caso difícil": "Petroperú anuncia nuevo directorio tras la renuncia del ministro de Energía y Minas",
}

st.set_page_config(page_title="Clasificador de titulares · El Comercio", page_icon="📰", layout="wide")


# ---------------------------------------------------------------------------
# Carga de datos y modelos (en caché: se leen una sola vez)
# ---------------------------------------------------------------------------
def sin_tildes(texto):
    # Para que la búsqueda por palabra no dependa de tildes ni mayúsculas ("peru" encuentra "Perú")
    normal = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in normal if not unicodedata.combining(c))


@st.cache_data
def cargar_noticias():
    noticias = pd.read_csv(DATOS / "noticias.csv", parse_dates=["fecha"])
    noticias["bajada"] = noticias["bajada"].fillna("")
    llm = pd.read_csv(DATOS / "etiquetas_llm.csv")[["titular", "etiqueta_llm", "confianza"]]
    particion = pd.read_csv(DATOS / "particion.csv")[["url", "particion"]]
    # Los merge "left" conservan el orden de noticias.csv, que es el mismo de embeddings_noticias.npy
    df = (noticias.merge(llm.rename(columns={"confianza": "confianza_llm"}), on="titular", how="left",
                         validate="one_to_one")
          .merge(particion, on="url", how="left", validate="one_to_one"))
    df["llm_coincide"] = df["etiqueta_llm"].eq(df["etiqueta"])
    df["texto_busqueda"] = (df["titular"] + " " + df["bajada"]).map(sin_tildes)
    return df


@st.cache_data
def cargar_resumen():
    metricas = json.loads((MODELO / "metricas.json").read_text(encoding="utf-8"))
    info = json.loads((MODELO / "info_entrenamiento.json").read_text(encoding="utf-8"))
    meta = json.loads((DATOS / "raw" / "metadatos_recoleccion.json").read_text(encoding="utf-8"))
    meta_llm = json.loads((DATOS / "etiquetas_llm_meta.json").read_text(encoding="utf-8"))
    n_crudas = len(pd.read_csv(DATOS / "raw" / "noticias_crudas.csv"))
    # La auditoría se hizo a mano en Excel: se acepta separador , o ; (igual que en el notebook 02)
    auditoria = pd.read_csv(DATOS / "auditoria_llm.csv", sep=None, engine="python", encoding="utf-8-sig",
                            dtype=str, keep_default_na=False)
    auditoria["coincide"] = (auditoria["etiqueta_llm"].str.strip().str.lower()
                             == auditoria["etiqueta_humana"].str.strip().str.lower())
    return metricas, info, meta, meta_llm, n_crudas, auditoria


@st.cache_data
def cargar_entidades():
    return pd.read_csv(DATOS / "entidades_ner.csv")


@st.cache_resource(show_spinner="Cargando el clasificador DistilBERT fine-tuned…")
def cargar_clasificador():
    """Devuelve (tokenizer, modelo, origen) o None si los pesos no están disponibles."""
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    from transformers.utils import logging as hf_logging

    hf_logging.set_verbosity_error()
    if (MODELO / "model.safetensors").exists():
        origen = str(MODELO)
    elif MODELO_HF:
        origen = MODELO_HF
    else:
        return None
    tokenizer = AutoTokenizer.from_pretrained(origen)
    modelo = AutoModelForSequenceClassification.from_pretrained(origen).eval()
    return tokenizer, modelo, origen


@st.cache_resource(show_spinner="Cargando el buscador semántico (solo la primera vez)…")
def cargar_buscador():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(MODELO_EMB), np.load(DATOS / "embeddings_noticias.npy")


def clasificar(titular, tokenizer, modelo, max_len):
    """Probabilidad de cada categoría para un titular (misma entrada que en el entrenamiento: solo el titular)."""
    import torch

    with torch.inference_mode():
        enc = tokenizer([titular], truncation=True, max_length=max_len, return_tensors="pt")
        prob = torch.softmax(modelo(**enc).logits, dim=-1)[0].numpy()
    return pd.Series(prob, index=[modelo.config.id2label[i] for i in range(len(prob))])


@st.cache_data(show_spinner=False)
def noticias_parecidas(titular, k=5):
    # Embeddings normalizados: la similitud coseno es el producto punto
    modelo_emb, emb = cargar_buscador()
    consulta = modelo_emb.encode([titular], normalize_embeddings=True)[0]
    similitud = emb @ consulta
    top = np.argsort(-similitud)[:k]
    return top, similitud[top]


# ---------------------------------------------------------------------------
# Gráficos
# ---------------------------------------------------------------------------
def barras_horizontales(valores, colores, texto, hover, titulo, opacidad=1.0, eje_x=None):
    fig = go.Figure(go.Bar(
        x=valores.values, y=valores.index, orientation="h", text=texto, textposition="outside",
        cliponaxis=False, hovertemplate=hover,
        marker=dict(color=colores, opacity=opacidad, cornerradius=4)))
    fig.update_layout(title=dict(text=titulo), height=110 + 46 * len(valores), bargap=0.45, showlegend=False,
                      margin=dict(l=10, r=50, t=80, b=40), yaxis_title=None, xaxis=eje_x or {})
    return fig


def grafico_categorias(df, columna):
    conteo = df[columna].value_counts().sort_values()
    pct = conteo / conteo.sum()
    mayor, menor = conteo.idxmax(), conteo.idxmin()
    fuente = "la sección editorial" if columna == "etiqueta" else "el LLM (Qwen2.5-1.5B)"
    if len(conteo) == 1:
        titulo = f"Toda la selección es de {NOMBRE[mayor]} ({conteo.max()} noticias)"
    elif conteo.max() - conteo.min() <= 0.1 * conteo.max():
        titulo = f"La selección está balanceada: entre {conteo.min()} y {conteo.max()} noticias por categoría"
    else:
        titulo = (f"{NOMBRE[mayor]} domina la selección ({pct.max():.0%}) y "
                  f"{NOMBRE[menor]} es la menos frecuente ({pct.min():.0%})")
    titulo += f"<br><sup>Noticias por categoría según {fuente} · {conteo.sum()} noticias filtradas</sup>"
    nombres = conteo.rename(index=NOMBRE)
    return barras_horizontales(
        nombres, [COLOR[c] for c in conteo.index], conteo.values,
        [f"<b>{NOMBRE[c]}</b><br>{n} noticias · {p:.0%} de la selección<extra></extra>"
         for c, n, p in zip(conteo.index, conteo.values, pct.values)],
        titulo, eje_x=dict(title="Noticias"))


def grafico_probabilidades(prob):
    prob = prob.sort_values()
    pred = prob.idxmax()
    return barras_horizontales(
        prob.rename(index=NOMBRE), [COLOR[c] for c in prob.index], [f"{p:.1%}" for p in prob.values],
        [f"<b>{NOMBRE[c]}</b><br>probabilidad {p:.2%}<extra></extra>" for c, p in prob.items()],
        f"El modelo asigna {prob.max():.0%} de probabilidad a {NOMBRE[pred]}"
        "<br><sup>Distribución softmax sobre las 4 categorías (suma 100 %)</sup>",
        opacidad=[1.0 if c == pred else 0.4 for c in prob.index],
        eje_x=dict(title="Probabilidad", tickformat=".0%", range=[0, 1.12]))


# ---------------------------------------------------------------------------
# Datos
# ---------------------------------------------------------------------------
df = cargar_noticias()
metricas, info, meta, meta_llm, n_crudas, auditoria = cargar_resumen()
ACUERDO, N_AUD = int(auditoria["coincide"].sum()), len(auditoria)
F1_TEST, F1_ZS, F1_LLM = metricas["f1_macro_test"], metricas["zero_shot_f1_macro_test"], metricas["llm_f1_macro_test"]
MEDIO = metricas["medio"]
FECHA_MIN, FECHA_MAX = df["fecha"].min().date(), df["fecha"].max().date()

# ---------------------------------------------------------------------------
# Barra lateral: filtros
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Filtros")
    medios = st.multiselect("Medio", sorted(df["medio"].unique()), default=sorted(df["medio"].unique()))
    categorias = st.multiselect("Categoría", ETIQUETAS, default=ETIQUETAS, format_func=NOMBRE.get,
                                help="Categoría derivada de la sección editorial de la nota (Parte 1).")
    rango = st.date_input("Fecha de publicación", value=(FECHA_MIN, FECHA_MAX),
                          min_value=FECHA_MIN, max_value=FECHA_MAX, format="DD/MM/YYYY")
    palabra = st.text_input("Buscar en titular o bajada", placeholder="ej. Congreso, dólar, Alianza")
    st.caption("Los filtros actualizan el gráfico, la tabla, la descarga y las entidades. "
               "Las métricas del modelo se calcularon sobre el test completo y no cambian.")

# Mientras se elige el rango en el calendario, date_input devuelve una sola fecha
desde, hasta = (rango[0], rango[-1]) if isinstance(rango, (tuple, list)) and rango else (FECHA_MIN, FECHA_MAX)
mascara = (df["medio"].isin(medios) & df["etiqueta"].isin(categorias)
           & df["fecha"].dt.date.between(desde, hasta))
if palabra.strip():
    mascara &= df["texto_busqueda"].str.contains(sin_tildes(palabra.strip()), regex=False)
filtrado = df[mascara]

# ---------------------------------------------------------------------------
# Encabezado y resumen metodológico
# ---------------------------------------------------------------------------
st.title("¿Pueden convertir titulares peruanos en un clasificador de noticias?")
st.markdown(
    f"**Sí.** Con {len(df)} titulares reales de **{MEDIO}**, un DistilBERT multilingüe ajustado en unos "
    f"{info['minutos_entrenamiento_cpu'][info['variante']]:.0f} minutos de CPU clasifica titulares nuevos en "
    f"4 categorías con **F1 macro {F1_TEST:.2f}** sobre un test que nunca vio, frente a {F1_ZS:.2f} de un "
    f"modelo zero-shot y {F1_LLM:.2f} de un LLM local.")

pasos = st.columns(4)
pasos[0].container(border=True).markdown(
    f"**1 · Recolección**  \nRSS y sitemaps oficiales de {MEDIO} con pausas de 1–2 s y `robots.txt` revisado. "
    f"{n_crudas:,} filas crudas → {len(df)} noticias limpias, mapeadas de la sección editorial a 4 categorías.")
pasos[1].container(border=True).markdown(
    f"**2 · Supervisión débil**  \nUn LLM local (`{meta_llm['modelo_llm'].split('/')[-1]}`) etiquetó los "
    f"{meta_llm['n_titulares']} titulares con un prompt estructurado y salida JSON. "
    f"Auditoría humana de {N_AUD} casos: {ACUERDO}/{N_AUD} de acuerdo.")
pasos[2].container(border=True).markdown(
    f"**3 · Fine-tuning**  \nSplit estratificado 70/15/15 (`random_state={info['semilla']}`). "
    f"`{info['modelo_base'].split('/')[-1]}` con `Trainer`, {info['epocas']} épocas, "
    f"elegido por F1 macro en validación.")
pasos[3].container(border=True).markdown(
    f"**4 · Evaluación y demo**  \nTest aislado de {metricas['n_test']} noticias: F1 macro {F1_TEST:.3f}, "
    f"accuracy {metricas['accuracy_test']:.3f}. Este dashboard explora los datos y clasifica titulares en vivo.")

# ---------------------------------------------------------------------------
# Indicadores clave
# ---------------------------------------------------------------------------
c1, c2, c3, c4 = st.columns(4)
c1.metric("Noticias recolectadas", f"{len(df):,}", border=True,
          help=f"Titulares de {MEDIO} publicados entre el {FECHA_MIN:%d/%m} y el {FECHA_MAX:%d/%m/%Y}, "
               f"tras limpiar {n_crudas:,} filas crudas (duplicados, secciones sin categoría y cupo por categoría).")
c2.metric("En la selección actual", f"{len(filtrado):,}", delta=f"{len(filtrado) / len(df):.0%} del total",
          delta_color="off", delta_arrow="off", border=True, help="Noticias que cumplen los filtros de la barra lateral.")
c3.metric("F1 macro en test", f"{F1_TEST:.3f}", delta=f"{F1_TEST - F1_ZS:+.2f} vs. zero-shot", border=True,
          help=f"{metricas['modelo_final']} evaluado sobre {metricas['n_test']} noticias de test nunca usadas para "
               f"entrenar ni elegir el modelo. Zero-shot ({metricas['zero_shot_modelo']}) en el mismo test: {F1_ZS:.3f}.")
c4.metric("Acuerdo LLM-humano",f"{ACUERDO / N_AUD:.0%}", delta=f"{ACUERDO} de {N_AUD} casos",
          delta_color="off", delta_arrow="off", border=True,
          help=f"{N_AUD} predicciones del LLM elegidas al azar y revisadas a mano (datos/auditoria_llm.csv).")

tab_datos, tab_probador, tab_ner, tab_modelos = st.tabs(
    ["📊 Explorar datos", "🧪 Probador en vivo", "🏷️ Entidades (NER)", "📘 Modelos y metodología"])

# ---------------------------------------------------------------------------
# Pestaña 1: visualización y tabla
# ---------------------------------------------------------------------------
with tab_datos:
    if filtrado.empty:
        st.warning("Ninguna noticia cumple los filtros. Amplía el rango de fechas o quita alguna condición.")
    else:
        origen = st.segmented_control(
            "Contar categorías según", ["etiqueta", "etiqueta_llm"], default="etiqueta", required=True,
            format_func={"etiqueta": "Sección editorial", "etiqueta_llm": "Etiqueta del LLM"}.get)
        izq, der = st.columns([1.5, 1])
        with izq:
            st.plotly_chart(grafico_categorias(filtrado, origen), key="grafico_categorias")
        with der:
            st.markdown("**¿Coincide el LLM con la sección editorial?**")
            acuerdo_cat = (filtrado.groupby("etiqueta")["llm_coincide"].agg(["mean", "size"])
                           .reindex([c for c in ETIQUETAS if c in categorias]).dropna())
            for cat, fila in acuerdo_cat.iterrows():
                st.progress(float(fila["mean"]), text=f"{NOMBRE[cat]}: {fila['mean']:.0%} de {int(fila['size'])} noticias")
            st.caption("En los desacuerdos no siempre se equivoca el LLM: la sección editorial también es una "
                       "etiqueta ruidosa (p. ej., notas de IA publicadas en Economía). Ver la pestaña de modelos.")

        st.subheader(f"Noticias filtradas ({len(filtrado)})")
        columnas = ["fecha", "etiqueta", "titular", "bajada", "etiqueta_llm", "confianza_llm", "llm_coincide",
                    "particion", "seccion_original", "medio", "url"]
        st.dataframe(
            filtrado[columnas], hide_index=True, height=420,
            column_config={
                "fecha": st.column_config.DatetimeColumn("Fecha", format="DD/MM/YYYY HH:mm"),
                "etiqueta": st.column_config.TextColumn("Categoría (sección)"),
                "titular": st.column_config.TextColumn("Titular", width="large"),
                "bajada": st.column_config.TextColumn("Bajada", width="medium"),
                "etiqueta_llm": st.column_config.TextColumn("Etiqueta LLM"),
                "confianza_llm": st.column_config.ProgressColumn("Confianza LLM", min_value=0.0, max_value=1.0,
                                                                 format="%.2f"),
                "llm_coincide": st.column_config.CheckboxColumn("LLM = sección"),
                "particion": st.column_config.TextColumn("Partición"),
                "seccion_original": st.column_config.TextColumn("Sección original"),
                "medio": st.column_config.TextColumn("Medio"),
                "url": st.column_config.LinkColumn("Nota", display_text="Abrir"),
            })
        st.download_button(
            "Descargar selección en CSV", filtrado[columnas].to_csv(index=False).encode("utf-8-sig"),
            file_name="noticias_filtradas.csv", mime="text/csv", icon=":material/download:")

# ---------------------------------------------------------------------------
# Pestaña 2: probador en vivo
# ---------------------------------------------------------------------------
with tab_probador:
    st.markdown("Escribe o pega un titular nuevo y el **DistilBERT fine-tuned** predice su categoría. "
                "Igual que en el entrenamiento, el modelo solo lee el titular (sin bajada).")
    try:
        clasificador = cargar_clasificador()
    except Exception as error:                       # p. ej., falta torch o no hay conexión para bajar el modelo
        clasificador = None
        st.error(f"No se pudo cargar el modelo: {error}")
    if clasificador is None:
        st.warning(
            "No se encontraron los pesos del modelo (`modelo/model.safetensors`, 541 MB, excluido de GitHub). "
            "Para generarlos ejecuta `02_clasificacion.ipynb`; para descargarlos de Hugging Face define la "
            "variable de entorno `MODELO_HF` con el id del repositorio del modelo.")

    def usar_ejemplo():
        if st.session_state.get("ejemplo"):
            st.session_state["titular"] = EJEMPLOS[st.session_state["ejemplo"]]

    st.pills("Probar con un ejemplo (titulares inventados, no están en el dataset)", list(EJEMPLOS),
             key="ejemplo", on_change=usar_ejemplo)
    with st.form("probador"):
        st.text_area("Titular", key="titular", height=90, max_chars=400,
                     placeholder="Ej.: Selección peruana anuncia su lista de convocados para las Eliminatorias")
        enviado = st.form_submit_button("Clasificar titular", type="primary", icon=":material/bolt:",
                                        disabled=clasificador is None)

    if enviado:
        texto = " ".join(st.session_state["titular"].split())
        if not texto:
            st.warning("Escribe un titular antes de clasificar.")
        else:
            tokenizer, modelo, _ = clasificador
            inicio = time.perf_counter()
            prob = clasificar(texto, tokenizer, modelo, info["max_length"])
            ms = (time.perf_counter() - inicio) * 1000
            st.session_state["resultado"] = {"titular": texto, "prob": prob, "ms": ms}
            st.session_state.setdefault("historial", []).insert(
                0, {"titular": texto, "categoría": NOMBRE[prob.idxmax()], "probabilidad": float(prob.max())})

    resultado = st.session_state.get("resultado")
    if resultado and clasificador is not None:
        prob = resultado["prob"]
        pred, p_max = prob.idxmax(), float(prob.max())
        st.markdown(f"> {resultado['titular']}")
        izq, der = st.columns([1, 1.6])
        with izq:
            st.metric("Categoría predicha", NOMBRE[pred], border=True)
            st.metric("Probabilidad", f"{p_max:.1%}", border=True)
            segunda = prob.drop(pred).idxmax()
            if p_max >= 0.9:
                st.success("Probabilidad alta: el titular usa vocabulario típico de la categoría.",
                           icon=":material/check_circle:")
            elif p_max >= 0.6:
                st.info(f"Confianza media: la segunda opción es {NOMBRE[segunda]} ({prob[segunda]:.0%}).",
                        icon=":material/info:")
            else:
                st.warning(f"Confianza baja: el titular mezcla temas ({NOMBRE[segunda]}: {prob[segunda]:.0%}) "
                           "o no pertenece a ninguna de las 4 categorías.", icon=":material/warning:")
            st.caption(f"Inferencia en {resultado['ms']:.0f} ms en CPU · máximo {info['max_length']} tokens. "
                       "El modelo tiende a ser sobreconfiado: en el test, sus 7 errores también tuvieron "
                       "probabilidades altas (0.76–0.99).")
        with der:
            st.plotly_chart(grafico_probabilidades(prob), key="grafico_probabilidades")

        st.subheader("Noticias más parecidas del dataset")
        st.caption("Buscador semántico de la Parte 1: similitud coseno entre embeddings multilingües "
                   f"(`{MODELO_EMB.split('/')[-1]}`). Sirve para ver de qué noticias reales está cerca el titular.")
        try:
            filas, similitud = noticias_parecidas(resultado["titular"])
            parecidas = df.iloc[filas][["titular", "etiqueta", "fecha", "url"]].assign(similitud=similitud)
            st.dataframe(parecidas, hide_index=True, column_config={
                "titular": st.column_config.TextColumn("Titular", width="large"),
                "etiqueta": st.column_config.TextColumn("Categoría (sección)"),
                "fecha": st.column_config.DatetimeColumn("Fecha", format="DD/MM/YYYY"),
                "url": st.column_config.LinkColumn("Nota", display_text="Abrir"),
                "similitud": st.column_config.ProgressColumn("Similitud coseno", min_value=0.0, max_value=1.0,
                                                             format="%.2f"),
            })
        except Exception as error:
            st.info(f"El buscador semántico no está disponible en este entorno ({type(error).__name__}).")

    if st.session_state.get("historial"):
        with st.expander(f"Titulares probados en esta sesión ({len(st.session_state['historial'])})"):
            st.dataframe(pd.DataFrame(st.session_state["historial"]), hide_index=True, column_config={
                "titular": st.column_config.TextColumn("Titular", width="large"),
                "probabilidad": st.column_config.ProgressColumn("Probabilidad", min_value=0.0, max_value=1.0,
                                                                format="%.2f"),
            })

# ---------------------------------------------------------------------------
# Pestaña 3: entidades nombradas (extra de la Parte 1)
# ---------------------------------------------------------------------------
with tab_ner:
    st.markdown("Entidades detectadas con `mrm8488/bert-spanish-cased-finetuned-ner` en titular + bajada "
                "(Parte 1). Se cuenta **en cuántas noticias** de la selección aparece cada una.")
    tipo = st.segmented_control("Tipo de entidad", list(TIPOS_NER), default="PER", required=True,
                                format_func=TIPOS_NER.get, key="tipo_ner")
    entidades = cargar_entidades()
    sel = entidades[entidades["url"].isin(filtrado["url"]) & entidades["tipo"].eq(tipo)]
    top = sel.groupby("entidad")["url"].nunique().sort_values(ascending=False).head(15).sort_values()
    if top.empty:
        st.info("No hay entidades de este tipo en la selección actual.")
    else:
        st.plotly_chart(barras_horizontales(
            top, COLOR[categorias[0]] if len(categorias) == 1 else ACENTO, top.values,
            "<b>%{y}</b><br>mencionada en %{x} noticias<extra></extra>",
            f"{top.index[-1]} es la entidad más mencionada entre las {TIPOS_NER[tipo].lower()} "
            f"({top.iloc[-1]} noticias)<br><sup>Top {len(top)} en las {len(filtrado)} noticias filtradas</sup>",
            eje_x=dict(title="Noticias que la mencionan")), key="grafico_ner")

# ---------------------------------------------------------------------------
# Pestaña 4: comparativa de modelos y detalles
# ---------------------------------------------------------------------------
with tab_modelos:
    st.markdown(f"Los tres enfoques se midieron sobre **las mismas {metricas['n_test']} noticias de test**, "
                "apartadas antes de cualquier decisión (no se usaron para el prompt, las épocas ni la elección del modelo).")
    comparativa = pd.DataFrame([
        {"enfoque": "Zero-shot NLI", "modelo": metricas["zero_shot_modelo"], "f1_macro": F1_ZS,
         "parámetros": "560 M", "entrenamiento": "Ninguno"},
        {"enfoque": "LLM (supervisión débil)", "modelo": metricas["llm_modelo"], "f1_macro": F1_LLM,
         "parámetros": "1 544 M", "entrenamiento": "Ninguno (solo prompt)"},
        {"enfoque": "DistilBERT fine-tuned", "modelo": info["modelo_base"], "f1_macro": F1_TEST,
         "parámetros": "135 M",
         "entrenamiento": f"{info['minutos_entrenamiento_cpu'][info['variante']]:.0f} min CPU + {info['n']['train']} titulares"},
    ])
    izq, der = st.columns([1, 1])
    with izq:
        f1 = comparativa.set_index("enfoque")["f1_macro"].sort_values()
        st.plotly_chart(barras_horizontales(
            f1, ACENTO, [f"{v:.2f}" for v in f1.values], "<b>%{y}</b><br>F1 macro %{x:.3f}<extra></extra>",
            f"El fine-tuning supera al zero-shot por {F1_TEST - F1_ZS:.2f} puntos de F1 macro"
            f"<br><sup>F1 macro en test (n={metricas['n_test']})</sup>",
            eje_x=dict(title="F1 macro", range=[0, 1.1])), key="grafico_modelos")
    with der:
        st.dataframe(comparativa, hide_index=True,
                     column_order=["enfoque", "f1_macro", "parámetros", "entrenamiento", "modelo"], column_config={
                         "enfoque": st.column_config.TextColumn("Enfoque"),
                         "f1_macro": st.column_config.NumberColumn("F1 macro (test)", format="%.3f"),
                         "parámetros": st.column_config.TextColumn("Parámetros"),
                         "entrenamiento": st.column_config.TextColumn("Costo de entrenamiento"),
                         "modelo": st.column_config.TextColumn("Modelo")})
        st.markdown(
            f"**Decisión:** DistilBERT fine-tuned. Es el más preciso, el más liviano y responde en menos de 0.1 s "
            f"por titular en CPU, frente a ~{meta_llm['seg_por_titular']:.1f} s del LLM. El LLM sigue siendo útil "
            "como **etiquetador**: un DistilBERT entrenado solo con sus etiquetas llegó a F1 0.80 en test.")

    with st.expander("Configuración del entrenamiento"):
        st.json(info)
    with st.expander(f"Auditoría humana del LLM ({ACUERDO}/{N_AUD} de acuerdo)"):
        st.dataframe(auditoria[["n", "titular", "etiqueta_llm", "confianza", "etiqueta_humana", "coincide", "comentario"]],
                     hide_index=True, column_config={
                         "titular": st.column_config.TextColumn("Titular", width="large"),
                         "coincide": st.column_config.CheckboxColumn("Coincide")})
    with st.expander("Prompt del LLM"):
        st.code(meta_llm["prompt_sistema"], language="text", wrap_lines=True)

st.divider()
st.caption(f"Fuente: {MEDIO} ({meta['base_url']}), RSS y sitemaps de noticias oficiales, recolectados el "
           f"{meta['fecha_recoleccion'][:10]}. Tarea 1 · Diplomado Data Science con Python, PUCP 2026 · "
           f"Cristian Moises Wong Pagan · [código en GitHub]({REPO}/tree/main/tarea_1)")
