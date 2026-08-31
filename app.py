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
    """Descarga y procesa una actividad. Retorna (nombre_arch, md, titulo, error)."""
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
    """Obtiene salud de un día. Retorna (nombre_arch, md, error)."""
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


def _pintar_resumen(resultados_act, resultados_salud, errores):
    """Pinta todo al final: resumen, descargas, contenidos colapsados."""
    st.divider()

    total = len(resultados_act) + len(resultados_salud)
    if errores:
        st.warning(f"✅ Proceso completado con {len(errores)} error(es) de {total + len(errores)} elementos.")
        with st.expander(f"⚠️ Errores ({len(errores)})", expanded=True):
            for err in errores:
                st.write(f"- {err}")
    else:
        st.success(f"✅ Proceso completado: {total} informe(s) generados sin errores.")

    # Descargas masivas arriba
    botones_descarga = []
    if resultados_act:
        pares = [(r[0], r[1]) for r in resultados_act]
        botones_descarga.append(("act", pares))
    if resultados_salud:
        pares = [(r[0], r[1]) for r in resultados_salud]
        botones_descarga.append(("sal", pares))

    if len(botones_descarga) == 2:
        col1, col2 = st.columns(2)
        cols = [col1, col2]
    elif len(botones_descarga) == 1:
        cols = [st.columns([1])[0]]
    else:
        cols = []

    for idx, (tipo, pares) in enumerate(botones_descarga):
        with cols[idx]:
            if tipo == "act":
                if len(pares) == 1:
                    st.download_button("📥 Descargar actividad", data=pares[0][1], file_name=pares[0][0],
                                       mime="text/markdown", key="dl_act_f", use_container_width=True)
                else:
                    st.download_button(f"📦 Descargar {len(pares)} actividades (ZIP)", data=_crear_zip(pares),
                                       file_name="actividades.zip", mime="application/zip",
                                       key="dl_act_z", use_container_width=True)
            else:
                if len(pares) == 1:
                    st.download_button("📥 Descargar salud", data=pares[0][1], file_name=pares[0][0],
                                       mime="text/markdown", key="dl_sal_f", use_container_width=True)
                else:
                    st.download_button(f"📦 Descargar {len(pares)} informes salud (ZIP)", data=_crear_zip(pares),
                                       file_name="salud.zip", mime="application/zip",
                                       key="dl_sal_z", use_container_width=True)

    # Contenido colapsado por actividad
    for i, (nombre_arch, md, titulo) in enumerate(resultados_act):
        with st.expander(f"🏃 {titulo}"):
            st.download_button(f"📥 {nombre_arch}", data=md, file_name=nombre_arch,
                               mime="text/markdown", key=f"dl_a_{i}")
            st.markdown(md)
            with st.expander("Ver Markdown en crudo"):
                st.code(md, language="markdown")

    # Contenido colapsado por día de salud
    for i, (nombre_arch, md, fecha) in enumerate(resultados_salud):
        with st.expander(f"🏥 Salud {fecha}"):
            st.download_button(f"📥 {nombre_arch}", data=md, file_name=nombre_arch,
                               mime="text/markdown", key=f"dl_s_{i}")
            st.markdown(md)
            with st.expander("Ver Markdown en crudo"):
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


# =========================================================================
# MODO 1: DATOS DE AYER
# =========================================================================
if modo == "📅 Datos de ayer":
    ayer = date.today() - timedelta(days=1)
    st.info(f"Se recuperarán actividades y datos de salud del **{ayer.isoformat()}**")

    if st.button("🚀 Obtener datos de ayer", type="primary"):
        garmin, error = _login_garmin()
        if error:
            st.error(error)
        else:
            # Fase 1: recoger todo con barra de progreso
            gc = _importar_garmin()
            actividades = gc.obtener_actividades_ayer(garmin)
            total = len(actividades) + 1

            progress_bar = st.progress(0)
            progress_text = st.empty()

            resultados_act = []
            resultados_salud = []
            errores = []

            for idx, act in enumerate(actividades):
                na, md, tit, err = _procesar_actividad(garmin, act, progress_bar, progress_text, idx + 1, total)
                if err:
                    errores.append(err)
                else:
                    resultados_act.append((na, md, tit))

            ns, ms, es = _obtener_salud(garmin, ayer.isoformat(), progress_bar, progress_text, total, total)
            if es:
                errores.append(es)
            else:
                resultados_salud.append((ns, ms, ayer.isoformat()))

            # Fase 2: limpiar progreso y pintar resultados
            progress_text.empty()
            progress_bar.empty()
            _pintar_resumen(resultados_act, resultados_salud, errores)


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
        horizontal=True,
        key="tipo_datos_rango",
    )

    if st.button("🚀 Procesar rango", type="primary"):
        st.session_state["rango_ejecutar"] = True
        st.session_state["rango_fecha_inicio"] = fecha_inicio
        st.session_state["rango_fecha_fin"] = fecha_fin
        st.session_state["rango_tipo"] = tipo_datos

    if st.session_state.get("rango_ejecutar"):
        f_ini = st.session_state["rango_fecha_inicio"]
        f_fin = st.session_state["rango_fecha_fin"]
        tipo = st.session_state["rango_tipo"]
        quiere_act = "Actividades" in tipo
        quiere_sal = "Salud" in tipo
        st.session_state["rango_ejecutar"] = False

        garmin, error = _login_garmin()
        if error:
            st.error(error)
        else:
            gc = _importar_garmin()

            # Fase 1: recoger todo
            actividades = []
            if quiere_act:
                actividades = gc.obtener_actividades_por_fecha(garmin, f_ini.isoformat(), f_fin.isoformat()) or []

            dias = (f_fin - f_ini).days + 1 if quiere_sal else 0
            total = len(actividades) + dias

            if total == 0:
                st.info("No se encontraron datos en el rango seleccionado.")
            else:
                progress_bar = st.progress(0)
                progress_text = st.empty()

                resultados_act = []
                resultados_salud = []
                errores = []
                paso = 0

                if quiere_act:
                    if actividades:
                        for act in actividades:
                            paso += 1
                            na, md, tit, err = _procesar_actividad(garmin, act, progress_bar, progress_text, paso, total)
                            if err:
                                errores.append(err)
                            else:
                                resultados_act.append((na, md, tit))
                    else:
                        st.info("No se encontraron actividades en el rango.")

                if quiere_sal:
                    fecha_actual = f_ini
                    while fecha_actual <= f_fin:
                        paso += 1
                        fs = fecha_actual.isoformat()
                        ns, ms, es = _obtener_salud(garmin, fs, progress_bar, progress_text, paso, total)
                        if es:
                            errores.append(es)
                        else:
                            resultados_salud.append((ns, ms, fs))
                        fecha_actual += timedelta(days=1)

                # Fase 2: limpiar progreso y pintar
                progress_text.empty()
                progress_bar.empty()
                _pintar_resumen(resultados_act, resultados_salud, errores)


# =========================================================================
# MODO 3: PROCESAR ARCHIVO .FIT MANUAL
# =========================================================================
elif modo == "📁 Procesar archivo .FIT":
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
                st.markdown(md)
                with st.expander("Ver Markdown en crudo"):
                    st.code(md, language="markdown")
                st.download_button("📥 Descargar .md", data=md, file_name=nombre_dl, mime="text/markdown")
            except Exception as e:
                st.error(f"Error: {e}")
            finally:
                if os.path.exists(ruta_temporal):
                    os.remove(ruta_temporal)
