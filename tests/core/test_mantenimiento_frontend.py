"""Tests de core.mantenimiento_frontend: clasificación de fallo + reporte."""

from pathlib import Path

from core.mantenimiento_frontend import (
    clasificar_fallo,
    generar_reporte_mantenimiento_frontend,
)


def test_clasifica_red_no_es_codigo():
    r = clasificar_fallo(
        estado="error", motivos=[], diagnostico={},
        excepcion="requests.exceptions.ConnectTimeout: timed out",
    )
    assert r["categoria"] == "RED_O_PORTAL_CAIDO"
    assert r["es_bug_de_codigo"] is False
    assert r["superficie"] == "RED"


def test_clasifica_anti_bot():
    r = clasificar_fallo(
        estado="sin_datos", motivos=["HTTP 403 forbidden"],
        diagnostico={}, excepcion=None,
    )
    assert r["categoria"] == "ANTI_BOT"
    assert r["superficie"] == "ANTI_BOT"


def test_clasifica_anti_bot_por_flag_diagnostico():
    r = clasificar_fallo(
        estado="sin_datos", motivos=[],
        diagnostico={"anti_bot": "Cloudflare challenge"}, excepcion=None,
    )
    assert r["categoria"] == "ANTI_BOT"


def test_clasifica_frontend_listado():
    r = clasificar_fallo(
        estado="sin_datos", motivos=[],
        diagnostico={"paginas_visitadas": 2, "tarjetas_totales": 0},
        excepcion=None,
    )
    assert r["categoria"] == "FRONTEND_LISTADO"
    assert r["superficie"] == "LISTADO"


def test_clasifica_cobertura_baja():
    r = clasificar_fallo(
        estado="degradado",
        motivos=["cobertura de precio por debajo del umbral"],
        diagnostico={"paginas_visitadas": 1, "tarjetas_totales": 5},
        excepcion=None,
    )
    assert r["categoria"] == "COBERTURA_BAJA"
    assert r["superficie"] == "LIMPIEZA"


def test_reporte_usa_superficie_por_categoria(tmp_path):
    ruta = generar_reporte_mantenimiento_frontend(
        portal="urbania", operacion="venta", estado="sin_datos",
        carpeta_reportes=str(tmp_path),
        diagnostico={"paginas_visitadas": 2, "tarjetas_totales": 0},
        superficie_por_categoria={
            "LISTADO": ["portal_scrapers/navent.py: scrape_listados"],
        },
    )
    texto = Path(ruta).read_text(encoding="utf-8")
    assert "FRONTEND_LISTADO" in texto
    assert "Tocar SOLO estos archivos" in texto
    assert "scrape_listados" in texto


def test_reporte_red_marca_no_tocar_codigo(tmp_path):
    ruta = generar_reporte_mantenimiento_frontend(
        portal="servir", operacion=None, estado="error",
        carpeta_reportes=str(tmp_path),
        excepcion="ConnectionError: Max retries exceeded",
    )
    texto = Path(ruta).read_text(encoding="utf-8")
    assert "RED_O_PORTAL_CAIDO" in texto
    assert "no es codigo" in texto.lower()
