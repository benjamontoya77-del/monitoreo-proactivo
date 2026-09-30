from app.services.sla import mttr_segundos, porcentaje_uptime


def test_uptime():
    assert porcentaje_uptime(996, 1000) == 99.6
    assert porcentaje_uptime(0, 0) is None


def test_mttr():
    assert mttr_segundos([30, 60, 90]) == 60
    assert mttr_segundos([]) is None
