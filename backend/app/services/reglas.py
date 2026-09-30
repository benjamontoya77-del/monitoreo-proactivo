"""Motor de reglas proactivo (funciones puras, fáciles de probar). Módulo de Alertas del Hito 1."""
from dataclasses import dataclass, field

from .scanner import Resultado


def valor_parametro(parametro: str, r: Resultado) -> float | None:
    return {"latencia_ms": r.latencia_ms, "uso_cpu_pct": r.cpu, "uso_ram_pct": r.ram,
            "interfaces_down": r.interfaces_down}.get(parametro)


def evaluar(parametro: str, umbral: float, r: Resultado) -> tuple[bool | None, float | None]:
    """(violada, valor). violada=None si la métrica no está disponible (no se evalúa)."""
    if parametro == "disponibilidad":
        return (not r.disponible), None
    valor = valor_parametro(parametro, r)
    if valor is None:
        return None, None
    return valor > umbral, valor


def describir(parametro: str, umbral: float, valor: float | None, nombre: str, ip: str) -> str:
    if parametro == "disponibilidad":
        return f"{nombre} ({ip}) no responde: servicio no disponible"
    return f"{nombre} ({ip}): {parametro} = {valor:g} supera el umbral de {umbral:g}"


@dataclass
class Decision:
    abrir: list = field(default_factory=list)      # [(regla, descripcion)]
    resolver: list = field(default_factory=list)   # [regla_id]


def decidir(reglas, ids_abiertas: set[int], r: Resultado, nombre: str, ip: str) -> Decision:
    """Deduplicación anti-fatiga: una regla solo abre una alerta si no tiene una abierta,
    y solo notifica en las transiciones (abrir / resolver)."""
    dec = Decision()
    for regla in reglas:
        if not regla.habilitada:
            continue
        violada, valor = evaluar(regla.parametro, regla.valor_umbral, r)
        if violada is None:
            continue
        if violada and regla.id not in ids_abiertas:
            dec.abrir.append((regla, describir(regla.parametro, regla.valor_umbral, valor, nombre, ip)))
        elif not violada and regla.id in ids_abiertas:
            dec.resolver.append(regla.id)
    return dec


def calcular_estado(disponible: bool, criticidades_abiertas: list[str]) -> str:
    if not disponible or "Crítica" in criticidades_abiertas:
        return "CRÍTICO"
    return "ALERTA" if criticidades_abiertas else "ACTIVO"
