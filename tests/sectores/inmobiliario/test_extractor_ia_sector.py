"""Tests de utilidades IA del sector inmobiliario."""

import pandas as pd

from sectores.inmobiliario.extractor_ia import asignar_publicacion_id


def test_asignar_publicacion_id_prefiere_posting_id():
    df = pd.DataFrame([
        {
            "portal": "urbania",
            "tipo_operacion": "venta",
            "posting_id": "149446471",
            "enlace": "https://urbania.pe/a?utm=1",
        }
    ])

    out = asignar_publicacion_id(df)

    assert out.loc[0, "publicacion_id"] == "urbania:venta:posting:149446471"


def test_asignar_publicacion_id_fallback_url_es_estable_ignorando_query():
    df = pd.DataFrame([
        {
            "portal": "properati",
            "tipo_operacion": "alquiler",
            "posting_id": None,
            "enlace": "https://properati.com.pe/a?utm=1#x",
        },
        {
            "portal": "properati",
            "tipo_operacion": "alquiler",
            "posting_id": None,
            "enlace": "https://properati.com.pe/a",
        },
    ])

    out = asignar_publicacion_id(df)

    assert out.loc[0, "publicacion_id"] == out.loc[1, "publicacion_id"]
    assert out.loc[0, "publicacion_id"].startswith("properati:alquiler:url:")
