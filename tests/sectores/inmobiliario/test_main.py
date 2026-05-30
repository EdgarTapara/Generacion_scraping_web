"""Tests de integración del orquestador `sectores.inmobiliario.main`.

Ejercitan el pipeline vigente del framework (scraping → limpieza →
publicacion_id → compuerta core.calidad → IA → historial → Excel) sin red:
se parchea sólo el scraping y la limpieza; el resto corre de verdad.
"""

import pandas as pd

from sectores.inmobiliario import main as main_mod


def _diag_navent_ok():
    return {
        "portal": "urbania", "operacion": "venta", "estrategia": "navent",
        "paginas_visitadas": 1, "paginas_con_tarjetas": 1, "tarjetas_totales": 1,
        "redux_paginas_ok": 1, "redux_paginas_fallidas": 0,
        "ratio_match_redux_dom": 1.0, "snapshots_html": [], "motivos_degradacion": [],
    }


def _df_sano():
    return pd.DataFrame([{
        "enlace": "https://urbania.pe/a-1",
        "posting_id": "URB-1",
        "portal": "urbania", "tipo_operacion": "venta",
        "tipo_inmueble": "casa", "distrito": "Cayma",
        "titulo": "Casa Cayma", "descripcion": "Linda casa",
        "precio": 200000.0, "moneda": "USD",
        "area_total_m2": 100.0, "dormitorios": 3, "banos": 2,
        "estacionamientos": 1, "pisos": 2, "anunciante": "X",
        "fecha_publicacion": "2026-04-22", "fecha_extraccion": "2026-04-22",
        "anio": 2026, "trimestre": "2026-T2", "mes": "2026-04",
    }])


def test_corrida_degradada_no_toca_historial_ni_ia(tmp_path, monkeypatch):
    """Cobertura insuficiente → degradado → ni IA ni historial; deja reporte."""
    df_pobre = pd.DataFrame([{
        "enlace": "https://urbania.pe/a", "precio": None,
        "distrito": None, "descripcion": "",
    }])

    monkeypatch.setattr(
        main_mod, "scrape_portal_con_diagnostico",
        lambda p, o, n, headless=False: ([{"enlace": "x"}], _diag_navent_ok()),
    )
    monkeypatch.setattr(main_mod, "pipeline_limpieza", lambda d, p, o: df_pobre)
    monkeypatch.setattr(main_mod, "asignar_publicacion_id", lambda df: df)
    monkeypatch.setattr(main_mod, "ia_disponible", lambda: True)
    monkeypatch.setattr(
        main_mod, "procesar_con_ia",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("IA no debe correr")),
    )
    historial_llamado = []
    monkeypatch.setattr(
        main_mod, "historial_registrar",
        lambda *a, **k: historial_llamado.append(True),
    )
    reportes = []
    monkeypatch.setattr(
        main_mod, "generar_reporte_mantenimiento_frontend",
        lambda **k: reportes.append(k["estado"]) or "ruta.md",
    )
    monkeypatch.setattr(main_mod, "_exportar_degradada", lambda df, p, o: None)

    df_out, stats = main_mod.ejecutar_scraping("urbania", "venta", 1, usar_ia=True)

    assert stats is None
    assert historial_llamado == []          # historial intacto
    assert reportes == ["degradado"]        # se generó el handoff


def test_corrida_sana_registra_historial_y_escribe_excel(tmp_path, monkeypatch):
    """Flujo completo OK: historial real (SQLite) + Excel acumulativo real."""
    monkeypatch.setattr(
        main_mod, "scrape_portal_con_diagnostico",
        lambda p, o, n, headless=False: ([{"enlace": "x"}], _diag_navent_ok()),
    )
    monkeypatch.setattr(main_mod, "pipeline_limpieza", lambda d, p, o: _df_sano())
    # Redirigir salidas a tmp_path (config se lee en tiempo de ejecución).
    monkeypatch.setattr(main_mod.config, "RUTA_DB", str(tmp_path / "h.db"))
    monkeypatch.setattr(main_mod.config, "CARPETA_SALIDA", str(tmp_path))

    df_out, stats = main_mod.ejecutar_scraping("urbania", "venta", 1, usar_ia=False)

    assert df_out is not None
    assert stats["nuevos"] == 1
    # El Excel institucional se escribió
    assert (tmp_path / "urbania_venta_historico.xlsx").exists()
    # El periodo llegó al snapshot SQLite
    import sqlite3
    with sqlite3.connect(tmp_path / "h.db") as conn:
        row = conn.execute('SELECT trimestre, mes FROM "anuncios"').fetchone()
    assert row == ("2026-T2", "2026-04")
