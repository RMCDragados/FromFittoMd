# =============================================================
# Lanzar FromFitToMd v2.0
# =============================================================

Write-Host ""
Write-Host "=== FromFitToMd v2.0 ===" -ForegroundColor Cyan
Write-Host ""

# Verificar dependencias
Write-Host "Verificando dependencias..." -ForegroundColor Yellow
pip install -r requirements.txt -q

# Verificar si las credenciales de Garmin estan configuradas
if ($env:GARMIN_KEY -and $env:GARMIN_EMAIL_ENC -and $env:GARMIN_PASS_ENC) {
    Write-Host "Credenciales de Garmin: OK" -ForegroundColor Green
} else {
    Write-Host "Credenciales de Garmin: NO configuradas" -ForegroundColor Yellow
    Write-Host "  Los modos 'Datos de ayer' y 'Rango de fechas' no funcionaran." -ForegroundColor Yellow
    Write-Host "  El modo 'Procesar archivo .FIT' si funciona sin credenciales." -ForegroundColor Yellow
    Write-Host "  Para configurar: .\setup_credenciales.ps1" -ForegroundColor Yellow
    Write-Host "  Luego copia set_env.example.ps1 a set_env.ps1 y rellena los valores." -ForegroundColor Yellow
    Write-Host ""
}

Write-Host "Iniciando aplicacion..." -ForegroundColor Green
Write-Host ""

python -m streamlit run app.py
