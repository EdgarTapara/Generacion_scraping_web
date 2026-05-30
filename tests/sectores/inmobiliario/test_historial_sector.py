"""Tests del adapter de historial inmobiliario."""

import sqlite3

import pandas as pd

from sectores.inmobiliario.historial import registrar_corrida


def _df_anuncio(fecha_publicacion="2026-04-10"):
    return pd.DataFrame([
        {
            "enlace": "https://urbania.pe/a",
            "posting_id": "URB-1",
            "publicacion_id": "urbania:venta:posting:URB-1",
            "fecha_publicacion": fecha_publicacion,
            "anio": 2026, "trimestre": "2026-T2", "mes": "2026-04",
            "titulo": "Casa en venta",
            "tipo_inmueble": "casa",
            "distrito": "Cayma",
            "nse": "Alto",
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
            "anunciante": "Inmobiliaria X",
            "precio_por_m2": 833.33,
            "latitud": None,
            "longitud": None,
        }
    ])


def test_historial_persiste_trazabilidad_y_periodo(tmp_path):
    """El snapshot persiste posting_id, publicacion_id y las columnas de periodo."""
    ruta = tmp_path / "h.db"

    registrar_corrida(_df_anuncio("2026-04-10"), "urbania", "venta", str(ruta), 3)

    with sqlite3.connect(ruta) as conn:
        row = conn.execute(
            'SELECT posting_id, publicacion_id, fecha_publicacion, '
            'anio, trimestre, mes, nse FROM "anuncios"'
        ).fetchone()

    assert row == (
        "URB-1", "urbania:venta:posting:URB-1", "2026-04-10",
        2026, "2026-T2", "2026-04", "Alto",
    )


def test_historial_ciclo_nuevo_luego_repetido(tmp_path):
    """Dos corridas con el mismo anuncio: nuevo → repetido (ciclo de vida core)."""
    ruta = tmp_path / "h.db"

    _, stats1 = registrar_corrida(_df_anuncio(), "urbania", "venta", str(ruta), 3)
    _, stats2 = registrar_corrida(_df_anuncio(), "urbania", "venta", str(ruta), 3)

    assert stats1["nuevos"] == 1
    assert stats2["repetidos"] == 1
    assert stats2["nuevos"] == 0
