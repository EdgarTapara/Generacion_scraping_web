"""Tests del adapter de historial inmobiliario."""

import sqlite3

import pandas as pd

from sectores.inmobiliario.historial import registrar_corrida


def _df_remax(fecha_publicacion=None):
    return pd.DataFrame([
        {
            "enlace": "https://www.remax.pe/a",
            "posting_id": "RMX-1",
            "publicacion_id": "remax:venta:posting:RMX-1",
            "fecha_publicacion": fecha_publicacion,
            "titulo": "Casa en venta",
            "tipo_inmueble": "casa",
            "distrito": "Cayma",
            "precio": 100000.0,
            "moneda": "USD",
            "precio_secundario": None,
            "moneda_secundaria": None,
            "area_total_m2": 120.0,
            "area_construida_m2": 100.0,
            "dormitorios": 3,
            "banos": 2,
            "estacionamientos": 1,
            "antiguedad_anos": None,
            "anunciante": "RE/MAX",
            "precio_por_m2": 833.33,
            "latitud": None,
            "longitud": None,
        }
    ])


def test_historial_inmobiliario_persiste_campos_de_trazabilidad(tmp_path):
    ruta = tmp_path / "h.db"

    registrar_corrida(_df_remax("2026-04-10"), "remax", "venta", str(ruta), 3)

    with sqlite3.connect(ruta) as conn:
        row = conn.execute(
            'SELECT posting_id, publicacion_id, fecha_publicacion FROM "anuncios"'
        ).fetchone()

    assert row == ("RMX-1", "remax:venta:posting:RMX-1", "2026-04-10")


def test_historial_remax_sin_fecha_usa_fecha_de_deteccion_y_la_conserva(tmp_path):
    ruta = tmp_path / "h.db"

    out1, stats1 = registrar_corrida(_df_remax(None), "remax", "venta", str(ruta), 3)
    out2, stats2 = registrar_corrida(_df_remax(None), "remax", "venta", str(ruta), 3)

    assert stats1["nuevos"] == 1
    assert stats2["repetidos"] == 1
    assert out1.loc[0, "fecha_publicacion"] == out2.loc[0, "fecha_publicacion"]
    assert isinstance(out1.loc[0, "fecha_publicacion"], str)
    assert len(out1.loc[0, "fecha_publicacion"]) == 10
