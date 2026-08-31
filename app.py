"""FromFitToMd v2.0 — Interfaz Streamlit con integración Garmin Connect.

Tres modos de operación:
1. Datos de ayer (actividades + salud del día anterior)
2. Rango de fechas (actividades y/o salud con descarga individual o en lote)
3. Procesar archivo .FIT manual (como v1)
"""

import io
import os
import shutil
import tempfile
import zipfile
from datetime import date, timedelta

import streamlit as st

import fitTOmd as ftm
import health_to_md as htm


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _importar_garmin():
    import garmin_client
    return garmin_client


def _login_garmin():
    gc = _importar_garmin()
    try:
        return gc.login_garmin(), None
    except EnvironmentError as e:
        return None, f"⚠️ Credenciales no configuradas: {e}"
    except Exception as e:
        return None, f"❌ Error de conexión: {e}"


def _procesar_actividad(garmin, actividad, progress_bar, progress_text, paso, total):
    gc = _importar_garmin()
    aid = str(actividad.get("activityId", ""))
    nombre = actividad.get("activityName", "Actividad")
    try:
        progress_text.markdown(f"**🏃 {nombre}** — 📋 Obteniendo metadata...")
        metadata = gc.obtener_metadata_actividad(garmin, aid)
        progress_text.markdown(f"**🏃 {nombre}** — 🌤️ Meteorología...")
        weather = gc.obtener_meteorologia_actividad(garmin, aid)
        progress_text.markdown(f"**🏃 {nombre}** — ⬇️ Descargando FIT...")
        ruta_fit = gc.descargar_fit_actividad(garmin, aid)
        try:
            progress_text.markdown(f"**🏃 {nombre}** — ⚙️ Procesando métricas...")
            md = ftm.procesar_archivo_temporal(ruta_fit, garmin_metadata=metadata, meteorologia=weather)
            fecha_str = str(actividad.get("startTimeLocal", ""))[:10]
            nombre_limpio = nombre.replace(" ", "_").replace("/", "-")[:40]
            nombre_arch = f"{fecha_str}_{nombre_limpio}.md"
            progress_bar.progress(paso / total)
            return nombre_arch, md, nombre, None
        finally:
            shutil.rmtree(os.path.dirname(ruta_fit), ignore_errors=True)
    except Exception as e:
        progress_bar.progress(paso / total)
        return None, None, nombre, f"Error procesando '{nombre}': {e}"


def _obtener_salud(garmin, fecha_str, progress_bar, progress_text, paso, total):
    try:
        datos = {"fecha": fecha_str}
        endpoints = [
            ("📊", "Estadísticas", "stats", lambda: garmin.get_stats(fecha_str)),
            ("❤️", "FC", "heart_rates", lambda: garmin.get_heart_rates(fecha_str)),
            ("😴", "Sueño", "sleep", lambda: garmin.get_sleep_data(fecha_str)),
            ("😤", "Estrés", "stress", lambda: garmin.get_stress_data(fecha_str)),
            ("🔋", "Body Battery", "body_battery", lambda: garmin.get_body_battery(fecha_str, fecha_str)),
            ("💓", "HRV", "hrv", lambda: garmin.get_hrv_data(fecha_str)),
            ("🫁", "SpO2", "spo2", lambda: garmin.get_spo2_data(fecha_str)),
            ("🌬️", "Respiración", "respiration", lambda: garmin.get_respiration_data(fecha_str)),
            ("⚡", "Intensidad", "intensity_minutes", lambda: garmin.get_intensity_minutes_data(fecha_str)),
            ("🎯", "Readiness", "training_readiness", lambda: garmin.get_training_readiness(fecha_str)),
            ("📈", "Status", "training_status", lambda: garmin.get_training_status(fecha_str)),
            ("⚖️", "Composición", "body_composition", lambda: garmin.get_body_composition(fecha_str, fecha_str)),
        ]
        n = len(endpoints)
        for i, (emoji, label, key, call) in enumerate(endpoints):
            progress_text.markdown(f"**🏥 Salud {fecha_str}** — {emoji} {label}... ({i+1}/{n})")
            try:
                datos[key] = call()
            except Exception:
                datos[key] = None
        progress_text.markdown(f"**🏥 Salud {fecha_str}** — 📝 Generando informe...")
        md = htm.generar_salud_md(datos)
        progress_bar.progress(paso / total)
        return f"salud_{fecha_str}.md", md, None
    except Exception as e:
        progress_bar.progress(paso / total)
        return None, None, f"Error salud {fecha_str}: {e}"


def _crear_zip(archivos):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for nombre, contenido in archivos:
            zf.writestr(nombre, contenido)
    return buf.getvalue()


def _recoger_datos(garmin, quiere_act, quiere_sal, f_ini, f_fin, progress_bar, progress_text):
    """Fase 1: recoger todos los datos con progreso. Retorna (act, sal, errores)."""
    gc = _importar_garmin()
    resultados_act = []
    resultados_salud = []
    errores = []

    actividades = []
    if quiere_act:
        progress_text.markdown("**🔍 Buscando actividades...**")
        actividades = gc.obtener_actividades_por_fecha(garmin, f_ini, f_fin) or []

    dias = (date.fromisoformat(f_fin) - date.fromisoformat(f_ini)).days + 1 if quiere_sal else 0
    total = len(actividades) + dias

    if total == 0:
        return [], [], ["No se encontraron datos en el rango."]

    paso = 0
    if quiere_act:
        for act in actividades:
            paso += 1
            na, md, tit, err = _procesar_actividad(garmin, act, progress_bar, progress_text, paso, total)
            if err:
                errores.append(err)
            else:
                resultados_act.append((na, md, tit))

    if quiere_sal:
        fecha_actual = date.fromisoformat(f_ini)
        fecha_fin_d = date.fromisoformat(f_fin)
        while fecha_actual <= fecha_fin_d:
            paso += 1
            fs = fecha_actual.isoformat()
            ns, ms, es = _obtener_salud(garmin, fs, progress_bar, progress_text, paso, total)
            if es:
                errores.append(es)
            else:
                resultados_salud.append((ns, ms, fs))
            fecha_actual += timedelta(days=1)

    return resultados_act, resultados_salud, errores


def _pintar_resumen(resultados_act, resultados_salud, errores, modo_salida="individual"):
    """Fase 2: pintar resultados desde session_state."""
    st.divider()

    total = len(resultados_act) + len(resultados_salud)
    if errores:
        st.warning(f"✅ Proceso completado con {len(errores)} error(es) de {total + len(errores)} elementos.")
        with st.expander(f"⚠️ Errores ({len(errores)})", expanded=True):
            for err in errores:
                st.write(f"- {err}")
    else:
        st.success(f"✅ Proceso completado: {total} informe(s) generados sin errores.")

    # --- Botones de descarga arriba ---
    if modo_salida == "consolidado":
        botones = []
        if resultados_act:
            md_all = "\n\n---\n\n".join(r[1] for r in resultados_act)
            botones.append(("act", "actividades_consolidado.md", md_all,
                           f"📥 Actividades ({len(resultados_act)}) en un .md"))
        if resultados_salud:
            md_all = "\n\n---\n\n".join(r[1] for r in resultados_salud)
            botones.append(("sal", "salud_consolidado.md", md_all,
                           f"📥 Salud ({len(resultados_salud)} días) en un .md"))
        if len(botones) == 2:
            c1, c2 = st.columns(2)
            cols = [c1, c2]
        elif len(botones) == 1:
            cols = [st.columns([1])[0]]
        else:
            cols = []
        for idx, (tipo, nombre, contenido, label) in enumerate(botones):
            with cols[idx]:
                st.download_button(label, data=contenido, file_name=nombre,
                                   mime="text/markdown", key=f"dl_{tipo}_cons", use_container_width=True)
    else:
        botones = []
        if resultados_act:
            pares = [(r[0], r[1]) for r in resultados_act]
            botones.append(("act", pares))
        if resultados_salud:
            pares = [(r[0], r[1]) for r in resultados_salud]
            botones.append(("sal", pares))
        if len(botones) == 2:
            c1, c2 = st.columns(2)
            cols = [c1, c2]
        elif len(botones) == 1:
            cols = [st.columns([1])[0]]
        else:
            cols = []
        for idx, (tipo, pares) in enumerate(botones):
            with cols[idx]:
                if len(pares) == 1:
                    lbl = "📥 Descargar actividad" if tipo == "act" else "📥 Descargar salud"
                    st.download_button(lbl, data=pares[0][1], file_name=pares[0][0],
                                       mime="text/markdown", key=f"dl_{tipo}_f", use_container_width=True)
                else:
                    lbl = f"📦 {len(pares)} actividades (ZIP)" if tipo == "act" else f"📦 {len(pares)} salud (ZIP)"
                    st.download_button(lbl, data=_crear_zip(pares), file_name=f"{tipo}.zip",
                                       mime="application/zip", key=f"dl_{tipo}_z", use_container_width=True)

    # --- Contenido en dos columnas: actividades izda, salud dcha ---
    if resultados_act and resultados_salud:
        col_act, col_sal = st.columns(2)
        with col_act:
            st.markdown("#### 🏃 Actividades")
            for i, (na, md, tit) in enumerate(resultados_act):
                with st.expander(tit):
                    if modo_salida == "individual":
                        st.download_button(f"📥 {na}", data=md, file_name=na,
                                           mime="text/markdown", key=f"dl_a_{i}")
                    st.markdown(md)
                    with st.expander("Markdown crudo"):
                        st.code(md, language="markdown")
        with col_sal:
            st.markdown("#### 🏥 Salud")
            for i, (na, md, fecha) in enumerate(resultados_salud):
                with st.expander(f"Salud {fecha}"):
                    if modo_salida == "individual":
                        st.download_button(f"📥 {na}", data=md, file_name=na,
                                           mime="text/markdown", key=f"dl_s_{i}")
                    st.markdown(md)
                    with st.expander("Markdown crudo"):
                        st.code(md, language="markdown")
    else:
        # Solo un tipo de datos: ancho completo
        for i, (na, md, tit) in enumerate(resultados_act):
            with st.expander(f"🏃 {tit}"):
                if modo_salida == "individual":
                    st.download_button(f"📥 {na}", data=md, file_name=na,
                                       mime="text/markdown", key=f"dl_a_{i}")
                st.markdown(md)
                with st.expander("Markdown crudo"):
                    st.code(md, language="markdown")
        for i, (na, md, fecha) in enumerate(resultados_salud):
            with st.expander(f"🏥 Salud {fecha}"):
                if modo_salida == "individual":
                    st.download_button(f"📥 {na}", data=md, file_name=na,
                                       mime="text/markdown", key=f"dl_s_{i}")
                st.markdown(md)
                with st.expander("Markdown crudo"):
                    st.code(md, language="markdown")


# ---------------------------------------------------------------------------
# Página principal
# ---------------------------------------------------------------------------

st.set_page_config(page_title="FromFitToMd v2.0", page_icon="⏱️", layout="wide")
st.title("⏱️ FromFitToMd v2.0")
st.caption("Procesador de entrenamientos y datos de salud de Garmin a Markdown")

modo = st.radio(
    "Selecciona el modo de operación:",
    ["📅 Datos de ayer", "📆 Rango de fechas", "📁 Procesar archivo .FIT"],
    horizontal=True,
)

# Inicializar session_state para resultados
for key in ["resultados_act", "resultados_salud", "errores", "modo_salida_resultado", "tiene_resultados"]:
    if key not in st.session_state:
        st.session_state[key] = [] if key != "tiene_resultados" else False


# =========================================================================
# MODO 1: DATOS DE AYER
# =========================================================================
if modo == "📅 Datos de ayer":
    ayer = date.today() - timedelta(days=1)
    st.info(f"Se recuperarán actividades y datos de salud del **{ayer.isoformat()}**")

    modo_salida = st.radio(
        "Formato de salida:",
        ["📄 Un archivo por elemento", "📋 Un solo archivo por tipo (consolidado)"],
        horizontal=True, key="modo_salida_ayer",
    )

    if st.button("🚀 Obtener datos de ayer", type="primary"):
        progress_bar = st.progress(0)
        progress_text = st.empty()
        progress_text.markdown("**🔐 Conectando a Garmin Connect...**")

        garmin, error = _login_garmin()
        if error:
            progress_text.empty()
            progress_bar.empty()
            st.error(error)
        else:
            act, sal, err = _recoger_datos(
                garmin, True, True, ayer.isoformat(), ayer.isoformat(),
                progress_bar, progress_text,
            )
            progress_text.empty()
            progress_bar.empty()

            # Guardar en session_state para que sobrevivan a re-renders
            st.session_state["resultados_act"] = act
            st.session_state["resultados_salud"] = sal
            st.session_state["errores"] = err
            st.session_state["modo_salida_resultado"] = "consolidado" if "consolidado" in modo_salida else "individual"
            st.session_state["tiene_resultados"] = True

    # Pintar resultados desde session_state (sobrevive a re-renders por descargas)
    if st.session_state.get("tiene_resultados"):
        _pintar_resumen(
            st.session_state["resultados_act"],
            st.session_state["resultados_salud"],
            st.session_state["errores"],
            st.session_state["modo_salida_resultado"],
        )


# =========================================================================
# MODO 2: RANGO DE FECHAS
# =========================================================================
elif modo == "📆 Rango de fechas":
    col1, col2 = st.columns(2)
    with col1:
        fecha_inicio = st.date_input("Fecha inicio", value=date.today() - timedelta(days=7), max_value=date.today())
    with col2:
        fecha_fin = st.date_input("Fecha fin", value=date.today() - timedelta(days=1), max_value=date.today())

    if fecha_inicio > fecha_fin:
        st.error("La fecha de inicio debe ser anterior a la fecha fin.")
        st.stop()

    tipo_datos = st.radio(
        "¿Qué datos quieres obtener?",
        ["🏃 Actividades y 🏥 Salud", "🏃 Solo Actividades", "🏥 Solo Salud"],
        horizontal=True, key="tipo_datos_rango",
    )
    modo_salida_rango = st.radio(
        "Formato de salida:",
        ["📄 Un archivo por elemento", "📋 Un solo archivo por tipo (consolidado)"],
        horizontal=True, key="modo_salida_rango",
    )

    if st.button("🚀 Procesar rango", type="primary"):
        st.session_state["rango_ejecutar"] = True
        st.session_state["rango_fecha_inicio"] = fecha_inicio.isoformat()
        st.session_state["rango_fecha_fin"] = fecha_fin.isoformat()
        st.session_state["rango_tipo"] = tipo_datos
        st.session_state["rango_modo_salida"] = modo_salida_rango

    if st.session_state.get("rango_ejecutar"):
        f_ini = st.session_state["rango_fecha_inicio"]
        f_fin = st.session_state["rango_fecha_fin"]
        tipo = st.session_state["rango_tipo"]
        quiere_act = "Actividades" in tipo
        quiere_sal = "Salud" in tipo
        ms = st.session_state.get("rango_modo_salida", "")
        st.session_state["rango_ejecutar"] = False

        progress_bar = st.progress(0)
        progress_text = st.empty()
        progress_text.markdown("**🔐 Conectando a Garmin Connect...**")

        garmin, error = _login_garmin()
        if error:
            progress_text.empty()
            progress_bar.empty()
            st.error(error)
        else:
            act, sal, err = _recoger_datos(
                garmin, quiere_act, quiere_sal, f_ini, f_fin,
                progress_bar, progress_text,
            )
            progress_text.empty()
            progress_bar.empty()

            st.session_state["resultados_act"] = act
            st.session_state["resultados_salud"] = sal
            st.session_state["errores"] = err
            st.session_state["modo_salida_resultado"] = "consolidado" if "consolidado" in ms else "individual"
            st.session_state["tiene_resultados"] = True

    if st.session_state.get("tiene_resultados"):
        _pintar_resumen(
            st.session_state["resultados_act"],
            st.session_state["resultados_salud"],
            st.session_state["errores"],
            st.session_state["modo_salida_resultado"],
        )


# =========================================================================
# MODO 3: PROCESAR ARCHIVO .FIT MANUAL
# =========================================================================
elif modo == "📁 Procesar archivo .FIT":
    # Limpiar resultados de modos anteriores al cambiar a modo manual
    st.session_state["tiene_resultados"] = False

    st.subheader("Datos de la actividad (opcional)")
    st.caption("Si el .fit contiene un nombre de entrenamiento programado, se usará. El título manual tiene prioridad.")

    titulo = st.text_input("Título de la actividad", placeholder="Ej: Tirada + 2km a umbral")
    notas = st.text_area("Notas de la sesión", placeholder="Ej: Sensaciones buenas. Calor moderado.", height=100)

    st.divider()
    archivo_subido = st.file_uploader("Selecciona o arrastra tu archivo .fit", type=["fit"])

    if archivo_subido is not None:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".fit") as tmp_file:
            tmp_file.write(archivo_subido.getvalue())
            ruta_temporal = tmp_file.name

        with st.spinner("⚙️ Procesando archivo FIT..."):
            try:
                md = ftm.procesar_archivo_temporal(
                    ruta_temporal,
                    titulo=titulo if titulo else None,
                    notas=notas if notas else None,
                )
                st.success("✅ Análisis completado!")
                nombre_dl = "informe_entrenamiento.md"
                if titulo and titulo.strip():
                    nombre_dl = titulo.strip().replace(" ", "_").replace("/", "-") + ".md"
                st.download_button("📥 Descargar .md", data=md, file_name=nombre_dl, mime="text/markdown")
                st.markdown(md)
                with st.expander("Ver Markdown en crudo"):
                    st.code(md, language="markdown")
            except Exception as e:
                st.error(f"Error: {e}")
            finally:
                if os.path.exists(ruta_temporal):
                    os.remove(ruta_temporal)
