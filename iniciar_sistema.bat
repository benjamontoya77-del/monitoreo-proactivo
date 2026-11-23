@echo off
title Motor de Monitoreo Proactivo TI - Hito 3
echo ================================================================
echo INICIANDO SISTEMA DE MONITOREO PROACTIVO Y ALERTA TEMPRANA (NOC)
echo ================================================================

cd /d "%~dp0"

echo [1/3] Verificando entorno virtual de ejecucion...
if exist "venv\Scripts\activate.bat" (
    call "venv\Scripts\activate.bat"
) else (
    echo [ADVERTENCIA] No se detecto 'venv' en la raiz. Verificando en backend...
    if exist "backend\venv\Scripts\activate.bat" (
        call "backend\venv\Scripts\activate.bat"
    )
)

echo [2/3] Levantando Backend FastAPI con motor asincrono (Uvicorn)...
start "Backend - Motor FastAPI" cmd /k "cd /d "%~dp0backend" && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"

echo [3/3] Esperando estabilizacion del servicio de API (3s)...
timeout /t 3 /nobreak >nul

echo Abriendo consola de control en el navegador...
start http://localhost:8000/
echo ================================================================
echo Sistema levantado con exito. Consola web y endpoints activos.
echo ================================================================
exit
