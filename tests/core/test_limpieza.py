"""Tests de core/limpieza/ — helpers genéricos."""

from datetime import datetime

from core.limpieza import (
    limpiar_fecha_relativa,
    limpiar_precio_pe,
    moneda_a_iso,
    parsear_entero,
    parsear_numero,
)


# -----------------------------
# numeros
# -----------------------------

def test_parsear_numero_basico():
    assert parsear_numero("S/ 2,460") == 2460.0
    assert parsear_numero("100.5 m²") == 100.5
    assert parsear_numero("1,234.56") == 1234.56


def test_parsear_numero_vacio():
    assert parsear_numero("") is None
    assert parsear_numero(None) is None
    assert parsear_numero("sin numeros aqui") is None


def test_parsear_entero():
    assert parsear_entero("3 dormitorios") == 3
    assert parsear_entero("hace 10 dias") == 10
    assert parsear_entero("sin numeros") is None


# -----------------------------
# moneda
# -----------------------------

def test_moneda_a_iso_soles():
    for v in ["S/", "S/.", "s/", "PEN", "soles", "SOLES"]:
        assert moneda_a_iso(v) == "PEN"


def test_moneda_a_iso_dolares():
    for v in ["USD", "US$", "$", "U$S", "dolares"]:
        assert moneda_a_iso(v) == "USD"


def test_moneda_a_iso_desconocida():
    assert moneda_a_iso("EUR") is None
    assert moneda_a_iso("") is None
    assert moneda_a_iso(None) is None


def test_limpiar_precio_pe_soles():
    r = limpiar_precio_pe("S/ 2,460")
    assert r["precio"] == 2460.0
    assert r["moneda"] == "PEN"
    assert r["precio_secundario"] is None


def test_limpiar_precio_pe_dual():
    r = limpiar_precio_pe("S/ 2,460 · USD 650")
    assert r["precio"] == 2460.0
    assert r["moneda"] == "PEN"
    assert r["precio_secundario"] == 650.0
    assert r["moneda_secundaria"] == "USD"


def test_limpiar_precio_pe_numero_pelado():
    """Fallback: número sin símbolo → asume soles."""
    r = limpiar_precio_pe("3500")
    assert r["precio"] == 3500.0
    assert r["moneda"] == "PEN"


def test_limpiar_precio_pe_vacio():
    r = limpiar_precio_pe(None)
    assert r["precio"] is None
    assert r["moneda"] is None


# -----------------------------
# fechas
# -----------------------------

_REF = datetime(2026, 4, 22)  # fecha fija para testing


def test_limpiar_fecha_hoy():
    assert limpiar_fecha_relativa("Publicado hoy", _REF) == "2026-04-22"


def test_limpiar_fecha_ayer():
    assert limpiar_fecha_relativa("Publicado desde ayer", _REF) == "2026-04-21"


def test_limpiar_fecha_hace_dias():
    assert limpiar_fecha_relativa("Publicado hace 3 dias", _REF) == "2026-04-19"


def test_limpiar_fecha_hace_semana_y_dias():
    # 1 semana (7) + 5 días = 12 días atrás
    assert limpiar_fecha_relativa("Publicado hace 1 semana, 5 dias", _REF) == "2026-04-10"


def test_limpiar_fecha_hace_meses():
    # 2 meses (60 días) atrás
    assert limpiar_fecha_relativa("hace 2 meses", _REF) == "2026-02-21"


def test_limpiar_fecha_hace_horas_es_hoy():
    assert limpiar_fecha_relativa("Publicado hace 5 horas", _REF) == "2026-04-22"


def test_limpiar_fecha_absoluta():
    assert limpiar_fecha_relativa("Publicado 23 may. 2022", _REF) == "2022-05-23"
    assert limpiar_fecha_relativa("6 ene. 2026", _REF) == "2026-01-06"


def test_limpiar_fecha_vacia():
    assert limpiar_fecha_relativa(None) is None
    assert limpiar_fecha_relativa("") is None
    assert limpiar_fecha_relativa("  texto sin fecha  ") is None
