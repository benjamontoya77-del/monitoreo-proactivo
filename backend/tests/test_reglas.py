"""Pruebas de unidad del motor de reglas (Hito 2, 3.3.3)."""
from types import SimpleNamespace as R

from app.services.reglas import calcular_estado, decidir, evaluar
from app.services.scanner import Resultado


def regla(id_, parametro, umbral, crit="Alta", hab=True):
    return R(id=id_, parametro=parametro, valor_umbral=umbral, criticidad=crit, habilitada=hab)


def test_umbral_superado():
    assert evaluar("latencia_ms", 150, Resultado(True, latencia_ms=200)) == (True, 200)
    assert evaluar("latencia_ms", 150, Resultado(True, latencia_ms=150)) == (False, 150)  # estricto (>)


def test_metrica_ausente_no_se_evalua():
    assert evaluar("uso_cpu_pct", 85, Resultado(True, latencia_ms=5)) == (None, None)


def test_disponibilidad():
    assert evaluar("disponibilidad", 1, Resultado(False))[0] is True
    assert evaluar("disponibilidad", 1, Resultado(True))[0] is False


def test_abre_una_sola_vez_sin_duplicar():
    r = Resultado(False)
    d1 = decidir([regla(1, "disponibilidad", 1, "Crítica")], set(), r, "SW", "10.0.0.1")
    assert len(d1.abrir) == 1 and "no responde" in d1.abrir[0][1]
    d2 = decidir([regla(1, "disponibilidad", 1, "Crítica")], {1}, r, "SW", "10.0.0.1")
    assert d2.abrir == [] and d2.resolver == []  # anti fatiga de alertas


def test_resuelve_al_normalizarse():
    d = decidir([regla(1, "latencia_ms", 150)], {1}, Resultado(True, latencia_ms=20), "SW", "10.0.0.1")
    assert d.resolver == [1]


def test_regla_deshabilitada_se_ignora():
    d = decidir([regla(1, "latencia_ms", 10, hab=False)], set(), Resultado(True, latencia_ms=999), "A", "1.1.1.1")
    assert d.abrir == []


def test_estado():
    assert calcular_estado(True, []) == "ACTIVO"
    assert calcular_estado(True, ["Alta"]) == "ALERTA"
    assert calcular_estado(True, ["Alta", "Crítica"]) == "CRÍTICO"
    assert calcular_estado(False, []) == "CRÍTICO"
    
def test_desactivar_regla_cierra_su_alerta_abierta():
    d = decidir([regla(1, "latencia_ms", 10, hab=False)], {1}, Resultado(True, latencia_ms=999), "A", "1.1.1.1")
    assert d.resolver == [1] and d.abrir == []