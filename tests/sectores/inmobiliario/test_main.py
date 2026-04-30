"""Tests del orquestador `sectores.inmobiliario.main`."""

import pandas as pd

from sectores.inmobiliario import main as main_mod


def test_contar_warnings_tolera_columna_ausente():
    df = pd.DataFrame([{"enlace": "https://x.com/1"}])
    assert main_mod._contar_warnings(df) == 0


def test_contar_warnings_ignora_nulos_y_blancos():
    df = pd.DataFrame([
        {"warnings": None},
        {"warnings": ""},
        {"warnings": "   "},
        {"warnings": "Precio fuera de rango"},
    ])
    assert main_mod._contar_warnings(df) == 1


def test_main_tolera_dataframes_sin_columna_warnings(monkeypatch, capsys):
    monkeypatch.setattr(main_mod, "configurar_logging", lambda carpeta_logs: None)
    monkeypatch.setattr(main_mod, "PORTALES_SOPORTADOS", ["urbania"])
    monkeypatch.setattr(
        main_mod,
        "ejecutar_scraping",
        lambda **kwargs: (
            pd.DataFrame([{"enlace": "https://x.com/1"}]),
            {"nuevos": 1, "repetidos": 0},
        ),
    )
    monkeypatch.setattr(
        main_mod,
        "generar_nombre_archivo_historico",
        lambda portal, operacion: "urbania_alquiler_historico.xlsx",
    )

    main_mod.main(["--portal", "urbania", "--operacion", "alquiler"])
    salida = capsys.readouterr().out

    assert "RESUMEN FINAL" in salida
    assert "urbania_alquiler_historico.xlsx" in salida
    assert "1 nuevos" in salida


def test_evaluar_calidad_navent_degradada_si_campos_criticos_vacios():
    df = pd.DataFrame([
        {
            "enlace": "https://urbania.pe/a",
            "precio": None,
            "distrito": None,
            "descripcion": "",
        }
    ])
    diagnostico = {
        "estrategia": "navent",
        "redux_paginas_ok": 0,
        "redux_paginas_fallidas": 1,
        "ratio_match_redux_dom": 0.0,
    }

    calidad = main_mod._evaluar_calidad_scraping("urbania", "venta", diagnostico, df)

    assert calidad["estado"] == "degradado"
    assert calidad["apta_para_historial"] is False
    assert calidad["motivos"]


def test_ejecutar_scraping_no_registra_historial_si_corrida_degradada(monkeypatch):
    df_limpio = pd.DataFrame([
        {
            "enlace": "https://urbania.pe/a",
            "precio": None,
            "distrito": None,
            "descripcion": "",
        }
    ])
    llamadas_historial = []

    monkeypatch.setattr(
        main_mod,
        "scrape_portal",
        lambda portal, operacion, num_paginas, headless=False: [{"enlace": "x"}],
    )
    monkeypatch.setattr(main_mod, "pipeline_limpieza", lambda datos, portal, operacion: df_limpio)
    monkeypatch.setattr(main_mod, "ia_disponible", lambda: True)
    monkeypatch.setattr(
        main_mod,
        "procesar_con_ia",
        lambda df: (_ for _ in ()).throw(AssertionError("IA no debe ejecutarse")),
    )
    monkeypatch.setattr(
        main_mod,
        "historial_registrar",
        lambda *args, **kwargs: llamadas_historial.append((args, kwargs)),
    )

    df_out, stats = main_mod.ejecutar_scraping(
        portal="urbania",
        operacion="venta",
        num_paginas=1,
    )

    assert df_out is not None
    assert stats is None
    assert llamadas_historial == []
