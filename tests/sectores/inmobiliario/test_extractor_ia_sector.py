"""Tests de utilidades IA del sector inmobiliario."""

import pandas as pd

from sectores.inmobiliario import extractor_ia
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


def test_extraer_ubicacion_usa_cache_y_evitar_llamada_ia(monkeypatch, tmp_path):
    llamadas = {"n": 0}

    class FakeExtractor:
        def disponible(self):
            return True

        def generar(self, prompt, max_reintentos=2):
            llamadas["n"] += 1
            return '[{"id": 0, "ubicacion": "Av. Ejercito 120"}]'

    monkeypatch.setattr(extractor_ia, "_extractor", FakeExtractor())

    df = pd.DataFrame([
        {
            "portal": "urbania",
            "tipo_operacion": "venta",
            "posting_id": "149446471",
            "enlace": "https://urbania.pe/a",
            "distrito": "Cayma",
            "descripcion": "Departamento amplio con buena ubicacion",
            "ubicacion": None,
        }
    ])
    ruta_cache = tmp_path / "historial.db"

    primera = extractor_ia.extraer_ubicacion_referencial(df.copy(), ruta_cache=str(ruta_cache))
    segunda = extractor_ia.extraer_ubicacion_referencial(df.copy(), ruta_cache=str(ruta_cache))

    assert primera.loc[0, "ubicacion"] == "Av. Ejercito 120"
    assert segunda.loc[0, "ubicacion"] == "Av. Ejercito 120"
    assert llamadas["n"] == 1


def test_extraer_ubicacion_reprocesa_si_cambia_descripcion(monkeypatch, tmp_path):
    respuestas = [
        '[{"id": 0, "ubicacion": "Av. Ejercito 120"}]',
        '[{"id": 0, "ubicacion": "Calle Mercaderes 10"}]',
    ]

    class FakeExtractor:
        def disponible(self):
            return True

        def generar(self, prompt, max_reintentos=2):
            return respuestas.pop(0)

    monkeypatch.setattr(extractor_ia, "_extractor", FakeExtractor())

    base = pd.DataFrame([
        {
            "portal": "urbania",
            "tipo_operacion": "venta",
            "posting_id": "149446471",
            "enlace": "https://urbania.pe/a",
            "distrito": "Cayma",
            "descripcion": "Departamento amplio con buena ubicacion",
            "ubicacion": None,
        }
    ])
    cambiado = base.copy()
    cambiado.loc[0, "descripcion"] = "Departamento renovado con vista urbana"
    ruta_cache = tmp_path / "historial.db"

    extractor_ia.extraer_ubicacion_referencial(base, ruta_cache=str(ruta_cache))
    out = extractor_ia.extraer_ubicacion_referencial(cambiado, ruta_cache=str(ruta_cache))

    assert out.loc[0, "ubicacion"] == "Calle Mercaderes 10"
    assert respuestas == []
