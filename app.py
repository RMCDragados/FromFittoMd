import streamlit as st
import tempfile
import os
import fitTOmd as ftm

# Configuracion basica de la pagina
st.set_page_config(page_title="Analizador FIT", page_icon="⏱️", layout="centered")

st.title("Procesador de Entrenamientos a Markdown")
st.write("Sube el archivo .fit de tu reloj o sensor para extraer los datos por vuelta y generar el informe para Copilot 365.")

# 1. Titulo y notas primero
st.subheader("Datos de la actividad (opcional)")
st.caption("Si el archivo .fit ya contiene un nombre de entrenamiento programado, se usara ese. El titulo que escribas aqui tiene prioridad.")

titulo = st.text_input(
    "Titulo de la actividad",
    placeholder="Ej: Tirada + 2km a umbral",
)

notas = st.text_area(
    "Notas de la sesion",
    placeholder="Ej: Sensaciones buenas, ultimos 2km a ritmo de umbral. Calor moderado.",
    height=100,
)

# 2. Archivo despues
st.divider()
archivo_subido = st.file_uploader("Selecciona o arrastra tu archivo .fit", type=["fit"])

if archivo_subido is not None:
    # 3. Manejo del archivo temporal
    with tempfile.NamedTemporaryFile(delete=False, suffix=".fit") as tmp_file:
        tmp_file.write(archivo_subido.getvalue())
        ruta_temporal = tmp_file.name

    st.info("Archivo cargado. Procesando metricas...")

    try:
        # 4. Procesar con titulo y notas personalizados
        markdown_final = ftm.procesar_archivo_temporal(
            ruta_temporal,
            titulo=titulo if titulo else None,
            notas=notas if notas else None,
        )

        st.success("Analisis completado!")

        # 5. Mostrar el resultado
        st.subheader("Vista previa del informe")
        st.markdown(markdown_final)

        st.divider()

        with st.expander("Ver Markdown en crudo (para copiar y pegar)"):
            st.code(markdown_final, language="markdown")

        # 6. Boton de descarga
        nombre_descarga = "informe_entrenamiento.md"
        if titulo and titulo.strip():
            nombre_descarga = titulo.strip().replace(" ", "_").replace("/", "-") + ".md"

        st.download_button(
            label="Descargar archivo .md",
            data=markdown_final,
            file_name=nombre_descarga,
            mime="text/markdown",
        )

    finally:
        # 7. Limpieza
        if os.path.exists(ruta_temporal):
            os.remove(ruta_temporal)
