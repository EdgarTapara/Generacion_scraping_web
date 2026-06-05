"""Tests de `core.calidad.detectar_duplicados` (señal, no borra)."""

import pandas as pd

from core.calidad import detectar_duplicados


def test_agrupa_mismo_anuncio_en_dos_fuentes():
    df = pd.DataFrame([
        {"fuente": "a", "anunciante": "Inmobiliaria Sur SAC",
         "titulo": "Departamento en Cayma 3 dormitorios", "zona": "arequipa", "monto": 350000},
        {"fuente": "b", "anunciante": "Inmobiliaria Sur",
         "titulo": "Depto Cayma 3 dormitorios", "zona": "arequipa", "monto": 352000},
        {"fuente": "a", "anunciante": "Otra Constructora",
         "titulo": "Casa de playa en Mejia", "zona": "arequipa", "monto": 800000},
    ])
    grupos = detectar_duplicados(
        df,
        campo_entidad="anunciante",
        campo_titulo="titulo",
        campo_region="zona",
        campo_valor="monto",
    )
    # Las dos primeras forman grupo; la tercera queda sola (None).
    assert grupos[0] is not None
    assert grupos[0] == grupos[1]
    assert grupos[2] is None


def test_distinta_region_no_agrupa():
    df = pd.DataFrame([
        {"anunciante": "ACME SAC", "titulo": "Analista de datos", "zona": "arequipa"},
        {"anunciante": "ACME SAC", "titulo": "Analista de datos", "zona": "lima"},
    ])
    grupos = detectar_duplicados(
        df, campo_entidad="anunciante", campo_titulo="titulo", campo_region="zona"
    )
    assert grupos == [None, None]


def test_sin_candidatos_devuelve_todos_none():
    df = pd.DataFrame([
        {"anunciante": "Empresa Uno", "titulo": "Contador senior"},
        {"anunciante": "Empresa Dos", "titulo": "Chofer categoria A"},
    ])
    grupos = detectar_duplicados(df, campo_entidad="anunciante", campo_titulo="titulo")
    assert grupos == [None, None]


def test_df_vacio():
    assert detectar_duplicados(pd.DataFrame(), campo_entidad="x", campo_titulo="y") == []
