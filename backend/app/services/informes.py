"""Informe de SLA en Excel (.xlsx) con formato listo para presentar/imprimir (Módulo de Reportabilidad)."""
import io
from datetime import datetime, timedelta, timezone

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

AZUL = PatternFill("solid", fgColor="1F3A5F")
VERDE = PatternFill("solid", fgColor="C6EFCE")
ROJO = PatternFill("solid", fgColor="FFC7CE")
GRIS = PatternFill("solid", fgColor="F2F2F2")
FINO = Side(style="thin", color="BFBFBF")
BORDE = Border(left=FINO, right=FINO, top=FINO, bottom=FINO)
BLANCO_NEGRITA = Font(bold=True, color="FFFFFF")


def fmt_dur(s) -> str:
    if s is None:
        return "—"
    s = int(s)
    if s < 60:
        return f"{s} s"
    if s < 3600:
        return f"{s // 60} min {s % 60} s"
    return f"{s // 3600} h {(s % 3600) // 60} min"


def _local(dt, tz_offset_min: int):
    """UTC (sin zona) -> hora local del navegador. `tz_offset_min` = Date.getTimezoneOffset() de JavaScript."""
    return dt - timedelta(minutes=tz_offset_min) if dt else None


def _encabezado(ws, fila: int, titulos: list[str]) -> None:
    for i, t in enumerate(titulos, start=1):
        c = ws.cell(row=fila, column=i, value=t)
        c.font, c.fill, c.border = BLANCO_NEGRITA, AZUL, BORDE
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.row_dimensions[fila].height = 30


def _anchos(ws, anchos: list[int]) -> None:
    for i, a in enumerate(anchos, start=1):
        ws.column_dimensions[get_column_letter(i)].width = a


def construir_xlsx(reporte: dict, incidentes: list[dict], tz_offset_min: int = 0) -> bytes:
    wb = Workbook()

    # ------------------------------------------------------------------ Resumen SLA
    ws = wb.active
    ws.title = "Resumen SLA"
    ahora_local = _local(datetime.now(timezone.utc).replace(tzinfo=None), tz_offset_min)
    ws["A1"] = "Informe de disponibilidad y cumplimiento de SLA"
    ws["A1"].font = Font(bold=True, size=14, color="1F3A5F")
    ws.merge_cells("A1:K1")
    ws["A2"] = (f"Período: últimos {reporte['dias']} día(s)  ·  Generado: {ahora_local:%d-%m-%Y %H:%M}  ·  "
                f"Objetivo de SLA: {reporte['sla_objetivo_pct']}%")
    ws.merge_cells("A2:K2")
    up = reporte.get("uptime_global_pct")
    sis = reporte.get("uptime_sistema_pct")
    ws["A3"] = (f"Uptime global: {'—' if up is None else f'{up}%'}  ·  MTTR global: {fmt_dur(reporte.get('mttr_global_s'))}"
                + (f"  ·  Disponibilidad del sistema de monitoreo: {sis}%" if sis is not None else ""))
    ws.merge_cells("A3:K3")
    for celda in ("A2", "A3"):
        ws[celda].font = Font(color="404040")

    titulos = ["Nodo", "IP", "Tipo", "Muestras", "Uptime (%)", "Downtime estimado", "Latencia prom. (ms)",
               "Latencia máx. (ms)", "Incidentes", "MTTR", "Cumple SLA"]
    _encabezado(ws, 5, titulos)
    fila = 6
    for n in reporte["nodos"]:
        cumple = n["cumple_sla"]
        valores = [n["nodo"], n["ip"], n["tipo"], n["muestras"], n["uptime_pct"], fmt_dur(n["downtime_estimado_s"]),
                   n["latencia_prom_ms"], n["latencia_max_ms"], n["incidentes"], fmt_dur(n["mttr_s"]),
                   "s/d" if cumple is None else ("CUMPLE" if cumple else "NO CUMPLE")]
        for col, v in enumerate(valores, start=1):
            c = ws.cell(row=fila, column=col, value=v)
            c.border = BORDE
            c.alignment = Alignment(horizontal="left" if col <= 3 else "center", vertical="center")
        ws.cell(row=fila, column=5).number_format = "0.000"
        res = ws.cell(row=fila, column=11)
        res.font = Font(bold=True)
        if cumple is not None:
            res.fill = VERDE if cumple else ROJO
        fila += 1
    if not reporte["nodos"]:
        ws.cell(row=6, column=1, value="No hay nodos registrados.")
    _anchos(ws, [26, 16, 12, 11, 12, 20, 14, 14, 11, 16, 14])
    ws.freeze_panes = "A6"
    if reporte["nodos"]:
        ws.auto_filter.ref = f"A5:K{fila - 1}"

    # ------------------------------------------------------------------ Incidentes
    wi = wb.create_sheet("Incidentes")
    wi["A1"] = f"Registro histórico de incidencias — últimos {reporte['dias']} día(s)"
    wi["A1"].font = Font(bold=True, size=13, color="1F3A5F")
    wi.merge_cells("A1:I1")
    _encabezado(wi, 3, ["N°", "Nodo", "IP", "Criticidad", "Descripción", "Inicio", "Fin", "Duración", "Estado"])
    f = 4
    for i in incidentes:
        valores = [i["id"], i["nodo"], i["ip"], i["criticidad"], i["descripcion"],
                   _local(i["fecha_hora_creacion"], tz_offset_min), _local(i["fecha_hora_resolucion"], tz_offset_min),
                   fmt_dur(i["duracion_s"]), i["estado_alerta"]]
        for col, v in enumerate(valores, start=1):
            c = wi.cell(row=f, column=col, value=v)
            c.border = BORDE
            c.alignment = Alignment(vertical="top", wrap_text=(col == 5))
            if col in (6, 7):
                c.number_format = "dd-mm-yyyy hh:mm:ss"
        est = wi.cell(row=f, column=9)
        est.fill = ROJO if i["estado_alerta"] == "ABIERTA" else VERDE
        est.font = Font(bold=True)
        f += 1
    if not incidentes:
        wi.cell(row=4, column=1, value="Sin incidentes en el período.")
    _anchos(wi, [7, 22, 16, 12, 60, 20, 20, 16, 12])
    wi.freeze_panes = "A4"
    if incidentes:
        wi.auto_filter.ref = f"A3:I{f - 1}"

    # ------------------------------------------------------------------ Notas metodológicas
    wn = wb.create_sheet("Notas")
    notas = [
        ("Cómo se calculan los indicadores", None),
        ("Muestras", "Cantidad de mediciones (ping/HTTP) del nodo dentro del período."),
        ("Uptime (%)", "Muestras en que el nodo estuvo disponible ÷ muestras totales × 100. Es una aproximación por muestreo: "
                       "su precisión depende de la frecuencia de escaneo."),
        ("Downtime estimado", "(100 − uptime) % × tiempo realmente observado (de la primera a la última muestra del período). "
                              "No se proyecta a todo el período."),
        ("MTTR", "Promedio de duración de las alertas resueltas creadas en el período (incluye cierres manuales)."),
        ("Cumple SLA", "CUMPLE si el uptime alcanza el objetivo configurado (SLA_OBJETIVO_PCT). s/d si no hay muestras."),
        ("Horas", "Las fechas se muestran en la hora local del equipo que generó el informe."),
    ]
    for r, (a, b) in enumerate(notas, start=1):
        wn.cell(row=r, column=1, value=a).font = Font(bold=True, size=12 if b is None else 11)
        if b:
            wn.cell(row=r, column=2, value=b).alignment = Alignment(wrap_text=True, vertical="top")
    _anchos(wn, [24, 100])

    for hoja in (ws, wi):
        hoja.page_setup.orientation = "landscape"
        hoja.page_setup.fitToWidth = 1
        hoja.page_setup.fitToHeight = 0
        hoja.sheet_properties.pageSetUpPr.fitToPage = True

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
