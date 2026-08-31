# =============================================================
# PLANTILLA de variables de entorno para Garmin Connect
#
# PASOS:
#   1. Copia este archivo: copy set_env.example.ps1 set_env.ps1
#   2. Ejecuta: .\setup_credenciales.ps1
#   3. Pega los valores generados en set_env.ps1
#   4. Ejecuta: .\set_env.ps1
#
# IMPORTANTE: Usa comillas SIMPLES para los valores.
# set_env.ps1 esta en .gitignore y no se subira al repo.
# =============================================================

$env:GARMIN_KEY = 'PEGA_AQUI_TU_CLAVE_FERNET'
$env:GARMIN_EMAIL_ENC = 'PEGA_AQUI_TU_EMAIL_CIFRADO'
$env:GARMIN_PASS_ENC = 'PEGA_AQUI_TU_PASSWORD_CIFRADO'
$env:GARMINTOKENS = "$HOME\.garminconnect"

Write-Host "Variables de entorno configuradas." -ForegroundColor Green

# Verificacion
python verificar_env.py
