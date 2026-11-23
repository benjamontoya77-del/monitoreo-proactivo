@echo off
title Respaldo Diario - Monitor Proactivo TI
echo Iniciando respaldo automatico de la base de datos...

:: 1. Generar marca de tiempo para el nombre del archivo 
set FECHA=%date:~-4,4%%date:~-7,2%%date:~-10,2%
set ARCHIVO="C:\Users\Benjamin\Desktop\Monitorproactivo\Respaldos\backup_%FECHA%.sql"

:: 2. Configurar credenciales 
set PGPASSWORD=cambia_esta_clave_db
set DB_USER=postgres
set DB_NAME=postgres

:: 3. Ejecutar pg_dump silenciosamente
pg_dump -U %DB_USER% -h 127.0.0.1 -p 5432 -F p -d %DB_NAME% -f %ARCHIVO%

echo Respaldo %ARCHIVO% completado con exito.