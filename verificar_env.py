"""Verifica que las variables de entorno de Garmin están configuradas correctamente."""

import os
import sys

def verificar():
    ok = True

    key = os.environ.get("GARMIN_KEY", "").strip()
    if not key:
        print("  GARMIN_KEY: VACIA")
        ok = False
    else:
        try:
            from cryptography.fernet import Fernet
            Fernet(key.encode())
            print(f"  GARMIN_KEY: OK ({len(key)} chars)")
        except Exception as e:
            print(f"  GARMIN_KEY: ERROR - {e}")
            print(f"  Longitud: {len(key)} (esperado: 44)")
            print("  Asegurate de usar comillas simples en set_env.ps1")
            ok = False

    email = os.environ.get("GARMIN_EMAIL_ENC", "").strip()
    if email:
        print(f"  GARMIN_EMAIL_ENC: OK ({len(email)} chars)")
    else:
        print("  GARMIN_EMAIL_ENC: VACIA")
        ok = False

    passw = os.environ.get("GARMIN_PASS_ENC", "").strip()
    if passw:
        print(f"  GARMIN_PASS_ENC: OK ({len(passw)} chars)")
    else:
        print("  GARMIN_PASS_ENC: VACIA")
        ok = False

    if ok:
        # Intentar descifrar
        try:
            from garmin_client import obtener_credenciales
            email_dec, _ = obtener_credenciales()
            print(f"  Descifrado: OK (email: {email_dec[:3]}...)")
        except Exception as e:
            print(f"  Descifrado: ERROR - {e}")
            ok = False

    return ok


if __name__ == "__main__":
    print()
    print("=== Verificacion de credenciales ===")
    if verificar():
        print("  Todo correcto!")
    else:
        print("  Hay problemas. Revisa los valores.")
    print()
