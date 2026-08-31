"""Cliente de Garmin Connect con credenciales cifradas y gestión de tokens.

Variables de entorno necesarias:
    GARMIN_KEY      — Clave Fernet para descifrar email/password
    GARMIN_EMAIL_ENC — Email cifrado con Fernet (base64)
    GARMIN_PASS_ENC  — Password cifrado con Fernet (base64)
    GARMINTOKENS     — Ruta para almacenar tokens (default: ~/.garminconnect)

Tras el primer login los tokens se reusan automáticamente.
"""

import io
import os
import sys
import zipfile
import tempfile
import logging
from datetime import date, datetime, timedelta
from pathlib import Path

from cryptography.fernet import Fernet
from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectNotFoundError,
    GarminConnectTooManyRequestsError,
)

logger = logging.getLogger(__name__)
logging.getLogger("garminconnect").setLevel(logging.WARNING)


# ---------------------------------------------------------------------------
# Cifrado / descifrado de credenciales
# ---------------------------------------------------------------------------

def generar_clave():
    """Genera una clave Fernet nueva. Ejecutar una sola vez y guardar como GARMIN_KEY."""
    return Fernet.generate_key().decode()


def cifrar_texto(texto: str, clave: str) -> str:
    """Cifra un texto con la clave Fernet y devuelve el resultado en base64."""
    f = Fernet(clave.encode())
    return f.encrypt(texto.encode()).decode()


def descifrar_texto(texto_cifrado: str, clave: str) -> str:
    """Descifra un texto cifrado con la clave Fernet."""
    f = Fernet(clave.encode())
    return f.decrypt(texto_cifrado.encode()).decode()


def obtener_credenciales() -> tuple[str, str]:
    """Obtiene y descifra las credenciales de las variables de entorno.

    Busca primero en variables de entorno (local) y luego en
    st.secrets (Streamlit Cloud).

    Retorna:
        (email, password) descifrados.

    Lanza:
        EnvironmentError si faltan credenciales en ambos sitios.
    """
    # Intentar desde variables de entorno
    clave = (os.environ.get("GARMIN_KEY") or "").strip()
    email_enc = (os.environ.get("GARMIN_EMAIL_ENC") or "").strip()
    pass_enc = (os.environ.get("GARMIN_PASS_ENC") or "").strip()

    # Fallback: Streamlit secrets (para Streamlit Cloud)
    if not all([clave, email_enc, pass_enc]):
        try:
            import streamlit as st
            clave = clave or st.secrets.get("GARMIN_KEY", "").strip()
            email_enc = email_enc or st.secrets.get("GARMIN_EMAIL_ENC", "").strip()
            pass_enc = pass_enc or st.secrets.get("GARMIN_PASS_ENC", "").strip()
        except Exception:
            pass

    if not all([clave, email_enc, pass_enc]):
        raise EnvironmentError(
            "Faltan variables de entorno: GARMIN_KEY, GARMIN_EMAIL_ENC, GARMIN_PASS_ENC. "
            "Configúralas en variables de entorno (local) o en Streamlit Secrets (Cloud)."
        )

    email = descifrar_texto(email_enc, clave)
    password = descifrar_texto(pass_enc, clave)
    return email, password


# ---------------------------------------------------------------------------
# Login y gestión de sesión
# ---------------------------------------------------------------------------

def login_garmin(prompt_mfa=None) -> Garmin:
    """Inicia sesión en Garmin Connect reutilizando tokens si existen.

    Args:
        prompt_mfa: Callable que devuelve el código MFA (para uso interactivo).

    Retorna:
        Instancia de Garmin autenticada.

    Lanza:
        GarminConnectAuthenticationError si las credenciales son incorrectas.
        EnvironmentError si faltan credenciales.
    """
    tokenstore = os.environ.get("GARMINTOKENS", "~/.garminconnect")
    # En Streamlit Cloud, usar /tmp si ~ no es escribible
    tokenstore_path = str(Path(tokenstore).expanduser())
    try:
        Path(tokenstore_path).mkdir(parents=True, exist_ok=True)
    except OSError:
        tokenstore_path = "/tmp/.garminconnect"
        Path(tokenstore_path).mkdir(parents=True, exist_ok=True)

    # Intentar con tokens guardados
    try:
        garmin = Garmin()
        garmin.login(tokenstore_path)
        logger.info("Login con tokens guardados exitoso.")
        return garmin
    except GarminConnectTooManyRequestsError:
        raise
    except (GarminConnectAuthenticationError, GarminConnectConnectionError, FileNotFoundError):
        logger.info("Tokens no válidos, intentando login con credenciales.")

    # Login fresco con credenciales cifradas
    email, password = obtener_credenciales()

    mfa_func = prompt_mfa or (lambda: input("Código MFA: ").strip())

    garmin = Garmin(
        email=email,
        password=password,
        prompt_mfa=mfa_func,
    )
    garmin.login(tokenstore_path)
    logger.info(f"Login exitoso. Tokens guardados en {tokenstore_path}")
    return garmin


# ---------------------------------------------------------------------------
# Descarga de actividades
# ---------------------------------------------------------------------------

def obtener_actividades_por_fecha(
    garmin: Garmin,
    fecha_inicio: str,
    fecha_fin: str | None = None,
) -> list[dict]:
    """Obtiene la lista de actividades en un rango de fechas.

    Args:
        garmin: Instancia autenticada.
        fecha_inicio: Fecha en formato "YYYY-MM-DD".
        fecha_fin: Fecha fin (inclusive). Si None, usa fecha_inicio.

    Retorna:
        Lista de diccionarios con metadata de cada actividad.
    """
    if fecha_fin is None:
        fecha_fin = fecha_inicio

    actividades = garmin.get_activities_by_date(fecha_inicio, fecha_fin)
    return actividades or []


def obtener_actividades_ayer(garmin: Garmin) -> list[dict]:
    """Obtiene las actividades del día anterior."""
    ayer = (date.today() - timedelta(days=1)).isoformat()
    return obtener_actividades_por_fecha(garmin, ayer)


def obtener_metadata_actividad(garmin: Garmin, activity_id: str) -> dict:
    """Obtiene metadata completa de una actividad (título, descripción, etc).

    Retorna dict con claves útiles:
        - activityName: título de la actividad en Garmin Connect
        - description: notas/descripción
        - activityId
        - startTimeLocal
        - distance, duration, averageHR, maxHR, etc.
    """
    return garmin.get_activity(activity_id)


def obtener_meteorologia_actividad(garmin: Garmin, activity_id: str) -> dict | None:
    """Obtiene datos meteorológicos de una actividad.

    Retorna dict con temperatura, humedad, viento, etc. o None si no hay datos.
    """
    try:
        weather = garmin.get_activity_weather(activity_id)
        return weather if weather else None
    except Exception:
        return None


def descargar_fit_actividad(garmin: Garmin, activity_id: str) -> str:
    """Descarga el .FIT de una actividad, lo descomprime y devuelve la ruta temporal.

    El archivo .FIT se guarda en un directorio temporal. El llamante es responsable
    de eliminar el archivo cuando termine.

    Retorna:
        Ruta al archivo .fit temporal.

    Lanza:
        ValueError si el zip no contiene un .fit.
    """
    # Descargar como ZIP
    zip_data = garmin.download_activity(
        activity_id,
        dl_fmt=Garmin.ActivityDownloadFormat.ORIGINAL,
    )

    # Descomprimir en memoria y extraer el .fit
    with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
        fit_files = [f for f in zf.namelist() if f.lower().endswith(".fit")]
        if not fit_files:
            raise ValueError(f"El zip de la actividad {activity_id} no contiene archivos .fit")

        # Extraer a temporal
        fit_name = fit_files[0]
        tmp_dir = tempfile.mkdtemp(prefix="garmin_fit_")
        ruta_fit = zf.extract(fit_name, tmp_dir)
        return ruta_fit


# ---------------------------------------------------------------------------
# Datos de salud
# ---------------------------------------------------------------------------

def obtener_datos_salud(garmin: Garmin, fecha: str) -> dict:
    """Obtiene todos los datos de salud disponibles para una fecha.

    Args:
        fecha: Fecha en formato "YYYY-MM-DD".

    Retorna:
        Diccionario con todas las métricas de salud del día.
    """
    datos = {"fecha": fecha}

    # Estadísticas generales (pasos, calorías, distancia, pisos)
    datos["stats"] = _safe_call(garmin.get_stats, fecha)

    # Frecuencia cardíaca
    datos["heart_rates"] = _safe_call(garmin.get_heart_rates, fecha)

    # Sueño
    datos["sleep"] = _safe_call(garmin.get_sleep_data, fecha)

    # Estrés
    datos["stress"] = _safe_call(garmin.get_stress_data, fecha)

    # Body Battery
    datos["body_battery"] = _safe_call(garmin.get_body_battery, fecha, fecha)

    # HRV (Variabilidad de la frecuencia cardíaca)
    datos["hrv"] = _safe_call(garmin.get_hrv_data, fecha)

    # SpO2
    datos["spo2"] = _safe_call(garmin.get_spo2_data, fecha)

    # Respiración
    datos["respiration"] = _safe_call(garmin.get_respiration_data, fecha)

    # Pisos
    datos["floors"] = _safe_call(garmin.get_floors, fecha)

    # Minutos de intensidad
    datos["intensity_minutes"] = _safe_call(garmin.get_intensity_minutes_data, fecha)

    # Hidratación
    datos["hydration"] = _safe_call(garmin.get_hydration_data, fecha)

    # Training Readiness
    datos["training_readiness"] = _safe_call(garmin.get_training_readiness, fecha)

    # Training Status
    datos["training_status"] = _safe_call(garmin.get_training_status, fecha)

    # Composición corporal
    datos["body_composition"] = _safe_call(garmin.get_body_composition, fecha, fecha)

    return datos


def _safe_call(method, *args, **kwargs):
    """Llama a un método de la API capturando errores. Devuelve None si falla."""
    try:
        result = method(*args, **kwargs)
        return result
    except (
        GarminConnectNotFoundError,
        GarminConnectAuthenticationError,
        GarminConnectTooManyRequestsError,
        GarminConnectConnectionError,
    ) as e:
        logger.warning(f"Error en {method.__name__}: {e}")
        return None
    except Exception as e:
        logger.warning(f"Error inesperado en {method.__name__}: {e}")
        return None


# ---------------------------------------------------------------------------
# Utilidad: configuración inicial de credenciales
# ---------------------------------------------------------------------------

def setup_credenciales():
    """Utilidad interactiva para generar la clave y cifrar credenciales.

    Imprime las variables de entorno que hay que configurar.
    """
    print("=== Configuración de credenciales cifradas para Garmin Connect ===\n")

    clave = Fernet.generate_key().decode()
    print(f"1. Clave generada (guardar como GARMIN_KEY):\n   {clave}\n")

    email = input("2. Introduce tu email de Garmin: ").strip()
    password = input("3. Introduce tu contraseña de Garmin: ").strip()

    email_enc = cifrar_texto(email, clave)
    password_enc = cifrar_texto(password, clave)

    print(f"\n4. Email cifrado (guardar como GARMIN_EMAIL_ENC):\n   {email_enc}\n")
    print(f"5. Password cifrado (guardar como GARMIN_PASS_ENC):\n   {password_enc}\n")

    print("=== Variables de entorno a configurar ===")
    print(f'GARMIN_KEY={clave}')
    print(f'GARMIN_EMAIL_ENC={email_enc}')
    print(f'GARMIN_PASS_ENC={password_enc}')
    print(f'GARMINTOKENS=~/.garminconnect')
    print("\nRecuerda NO subir estas variables a repositorios públicos.")


if __name__ == "__main__":
    setup_credenciales()
