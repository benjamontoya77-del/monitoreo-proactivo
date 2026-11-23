"""Pruebas del informe Excel (Módulo de Reportabilidad)."""
import io
from datetime import datetime

from openpyxl import load_workbook

from app.services.informes import construir_xlsx, fmt_dur

REPORTE = {
    "dias": 7, "sla_objetivo_pct": 99.0, "uptime_global_pct": 66.667, "mttr_global_s": 125,
    "nodos": [
        {"dispositivo_id": 1, "nodo": "DNS Primario Google", "ip": "8.8.8.8", "tipo": "Servidor", "muestras": 232,
         "uptime_pct": 100.0, "periodo_observado_s": 3480, "downtime_estimado_s": 0, "latencia_prom_ms": 9.3,
         "latencia_max_ms": 26, "incidentes": 0, "mttr_s": None, "cumple_sla": True},
        {"dispositivo_id": 2, "nodo": "Servidor caído", "ip": "198.51.199.1", "tipo": "Servidor", "muestras": 31,
         "uptime_pct": 0.0, "periodo_observado_s": 450, "downtime_estimado_s": 450, "latencia_prom_ms": None,
         "latencia_max_ms": None, "incidentes": 1, "mttr_s": 125, "cumple_sla": False},
        {"dispositivo_id": 3, "nodo": "Sin datos", "ip": "1.1.1.1", "tipo": "Router", "muestras": 0,
         "uptime_pct": None, "periodo_observado_s": 0, "downtime_estimado_s": None, "latencia_prom_ms": None,
         "latencia_max_ms": None, "incidentes": 0, "mttr_s": None, "cumple_sla": None},
    ],
}
INCIDENTES = [{"id": 45, "dispositivo_id": 2, "nodo": "Servidor caído", "ip": "198.51.199.1", "parametro": "disponibilidad",
               "criticidad": "Crítica", "descripcion": "Servidor caído no responde", "estado_alerta": "ABIERTA",
               "fecha_hora_creacion": datetime(2026, 11, 15, 23, 3, 1), "fecha_hora_resolucion": None,
               "duracion_s": None, "correlacionada": False}]


def test_fmt_dur():
    assert fmt_dur(None) == "—" and fmt_dur(45) == "45 s" and fmt_dur(125) == "2 min 5 s" and fmt_dur(3725) == "1 h 2 min"


def test_excel_tiene_las_tres_hojas_y_los_datos():
    wb = load_workbook(io.BytesIO(construir_xlsx(REPORTE, INCIDENTES, 180)))
    assert wb.sheetnames == ["Resumen SLA", "Incidentes", "Notas"]
    ws = wb["Resumen SLA"]
    assert ws["A5"].value == "Nodo" and ws["A6"].value == "DNS Primario Google"
    assert ws["K6"].value == "CUMPLE" and ws["K7"].value == "NO CUMPLE" and ws["K8"].value == "s/d"
    assert ws["F7"].value == "7 min 30 s"


def test_excel_convierte_la_hora_a_local():
    wb = load_workbook(io.BytesIO(construir_xlsx(REPORTE, INCIDENTES, 180)))   # Chile: UTC-3 -> offset 180
    assert wb["Incidentes"]["F4"].value == datetime(2026, 11, 15, 20, 3, 1)


def test_excel_sin_datos_no_falla():
    vacio = {"dias": 1, "sla_objetivo_pct": 99.0, "uptime_global_pct": None, "mttr_global_s": None, "nodos": []}
    wb = load_workbook(io.BytesIO(construir_xlsx(vacio, [], 0)))
    assert wb["Resumen SLA"]["A6"].value == "No hay nodos registrados."
    assert wb["Incidentes"]["A4"].value == "Sin incidentes en el período."
