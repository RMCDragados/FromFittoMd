# =============================================================
# Setup de credenciales cifradas para Garmin Connect
# Ejecutar una sola vez para generar las variables de entorno
# =============================================================

Write-Host ""
Write-Host "=== FromFitToMd - Configuracion de credenciales ===" -ForegroundColor Cyan
Write-Host ""

python garmin_client.py

Write-Host ""
Write-Host "=== INSTRUCCIONES ===" -ForegroundColor Yellow
Write-Host "Copia las 3 variables de arriba y pegalas en tu perfil de PowerShell"
Write-Host "o ejecutalas directamente en la terminal antes de lanzar la app."
Write-Host ""
Write-Host "Para que sean permanentes, anadelas a tu perfil:" -ForegroundColor Yellow
Write-Host "  notepad `$PROFILE"
Write-Host ""

pause
