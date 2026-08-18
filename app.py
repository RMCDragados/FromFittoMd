import streamlit as st
import tempfile
import os
import fitTOmd as ftm
# Aquí importarías las librerías de tu script actual
# import fitparse 
# from mi_script import extraer_metricas_cientificas

# Configuración básica de la página
st.set_page_config(page_title="Analizador FIT", page_icon="⏱️", layout="centered")

st.title("Procesador de Entrenamientos a Markdown")
st.write("Sube el archivo .fit de tu reloj o sensor para extraer los datos por vuelta y generar el informe para Copilot 365.")

# 1. El widget para subir el archivo
archivo_subido = st.file_uploader("Selecciona o arrastra tu archivo .fit", type=["fit"])

if archivo_subido is not None:
    # 2. Manejo del archivo temporal
    # Creamos un archivo temporal físico para que tu script original pueda leerlo
    with tempfile.NamedTemporaryFile(delete=False, suffix=".fit") as tmp_file:
        tmp_file.write(archivo_subido.getvalue())
        ruta_temporal = tmp_file.name

    st.info("Archivo cargado. Procesando métricas...")

    try:
        # ==========================================
        # 3. AQUÍ VA TU LÓGICA ACTUAL
        # Llama a tus funciones pasándole 'ruta_temporal'
        # ==========================================
        
        # Ejemplo:
        # markdown_final = extraer_metricas_cientificas(ruta_temporal)
        markdown_final = ftm.procesar_archivo_temporal(ruta_temporal)

        st.success("¡Análisis completado!")

        # 4. Mostrar el resultado
        st.subheader("Vista previa del informe")
        
        # Esto renderiza el Markdown para que veas cómo quedará
        st.markdown(markdown_final) 

        st.divider()

        # Ocultamos el texto en crudo en un desplegable para no saturar la pantalla
        with st.expander("Ver Markdown en crudo (para copiar y pegar)"):
            st.code(markdown_final, language="markdown")

        # 5. Botón de descarga
        # Permite descargar el .md directamente a tu móvil o tablet
        st.download_button(
            label="Descargar archivo .md",
            data=markdown_final,
            file_name="informe_entrenamiento.md",
            mime="text/markdown"
        )

    finally:
        # 6. Limpieza
        # Es vital borrar el archivo temporal para no llenar la memoria del servidor
        if os.path.exists(ruta_temporal):
            os.remove(ruta_temporal)