import asyncio
import csv
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.models import AlertaLog, Dispositivo
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

# PUENTE DIRECTO A DOCKER
DB_URL = "postgresql+asyncpg://monitor:cambia_esta_clave_db@127.0.0.1:5432/monitoreo"

engine = create_async_engine(DB_URL, echo=False)
SessionLocalDirecta = async_sessionmaker(engine, expire_on_commit=False)

async def generar_reporte():
    print("Analizando tiempos de respuesta REALES en la base de datos...")
    async with SessionLocalDirecta() as db:
        query_alertas = select(AlertaLog).order_by(AlertaLog.id.desc()).limit(30)
        result = await db.execute(query_alertas)
        alertas = result.scalars().all()
        
        archivo_csv = "Anexo_C_Resultados.csv"
        with open(archivo_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Nro", "Escenario", "Nodo", "t0 (Deteccion)", "t1 (Envio API)", "Tdet (Segundos)", "Oportuna (<60s)", "Canal"])
            
            for i, a in enumerate(alertas, 1):
                nodo_nombre = "Desconocido"
                if a.dispositivo_id:
                    disp = await db.get(Dispositivo, a.dispositivo_id)
                    if disp:
                        nodo_nombre = disp.nombre

                t0 = a.fecha_hora_creacion
                t1 = a.fecha_hora_envio
                
                if t0 and t1:
                    tdet = round((t1 - t0).total_seconds(), 2)
                    oportuna = "SÍ" if tdet < 60 else "NO"
                else:
                    tdet = "Pendiente / N/A"
                    oportuna = "-"
                    
                writer.writerow([i, a.descripcion[:25] + "...", nodo_nombre, t0, t1, tdet, oportuna, a.canal_envio])
                
    print(f"¡Éxito! Archivo '{archivo_csv}' generado con datos 100% EMPÍRICOS.")

if __name__ == "__main__":
    asyncio.run(generar_reporte())