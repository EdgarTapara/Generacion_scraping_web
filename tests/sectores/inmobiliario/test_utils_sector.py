"""Tests de parsers específicos del sector (Redux helpers + descripción)."""

import json
from pathlib import Path

from sectores.inmobiliario.modelos import DISTRITOS_NORM
from sectores.inmobiliario.utils_sector import (
    detectar_tipo_inmueble_fallback,
    extraer_antiguedad_descripcion,
    extraer_distrito_dom,
    extraer_distrito_redux,
    extraer_medio_banos_descripcion,
    extraer_pisos_descripcion,
    extraer_precio_redux,
    extraer_ubicacion_referencial_regex,
    mapear_main_features,
    parsear_features_tarjeta,
)

FIXTURE = Path(__file__).parent.parent.parent / "fixtures" / "navent" / "posting_sample.json"


def _posting():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


# -----------------------------
# Redux parsers (sobre fixture)
# -----------------------------

def test_mapear_main_features_fixture():
    p = _posting()
    r = mapear_main_features(p["mainFeatures"])
    assert r["area_total_m2"] == 120.0
    assert r["area_construida_m2"] == 100.0
    assert r["dormitorios"] == 3
    assert r["banos"] == 2
    assert r["estacionamientos"] == 1
    assert r["antiguedad_anos"] == 5


def test_extraer_precio_redux_primario_pen_secundario_usd():
    p = _posting()
    r = extraer_precio_redux(p["priceOperationTypes"], "alquiler")
    assert r["precio"] == 2500.0
    assert r["moneda"] == "PEN"
    assert r["precio_secundario"] == 650.0
    assert r["moneda_secundaria"] == "USD"


def test_extraer_precio_redux_sin_match_toma_primero():
    price_ops = [
        {"operationType": {"name": "Venta"},
         "prices": [{"amount": 50000, "currency": "USD"}]}
    ]
    r = extraer_precio_redux(price_ops, "alquiler")
    # No hay match por operación → fallback al primero
    assert r["precio"] == 50000.0
    assert r["moneda"] == "USD"


def test_extraer_distrito_redux_jerarquia():
    p = _posting()
    r = extraer_distrito_redux(p["postingLocation"], DISTRITOS_NORM)
    assert r["distrito"] == "Cayma"
    assert r["zone_name"] == "Los Angeles De Cayma"
    assert r["address_name"] == "Av. Ejercito 120"


def test_extraer_distrito_redux_address_oculta_se_ignora():
    loc = {
        "address": {"name": "Av. Secreta", "visibility": "PRIVATE"},
        "location": {"name": "Cayma", "label": "SUBAREA1"},
    }
    r = extraer_distrito_redux(loc, DISTRITOS_NORM)
    assert r["address_name"] is None
    assert r["distrito"] == "Cayma"


# -----------------------------
# Features tarjeta
# -----------------------------

def test_parsear_features_tarjeta_completo():
    r = parsear_features_tarjeta("247 m² tot. 3 dorm. 4 baños 1 estac.")
    assert r == {
        "area_total_m2": 247.0,
        "dormitorios": 3,
        "banos": 4,
        "estacionamientos": 1,
    }


# -----------------------------
# Parsers de descripción
# -----------------------------

def test_extraer_pisos_casa_de_n_pisos():
    assert extraer_pisos_descripcion("hermosa casa de 3 pisos con jardín") == 3


def test_extraer_pisos_palabra_en_texto():
    assert extraer_pisos_descripcion("casa de dos pisos y patio") == 2


def test_extraer_medio_banos_cantidad():
    assert extraer_medio_banos_descripcion("la propiedad cuenta con 2 medios baños") == 2


def test_extraer_medio_banos_bano_de_visitas():
    assert extraer_medio_banos_descripcion("depa con baño de visitas incluido") == 1


def test_extraer_antiguedad_a_estrenar_es_cero():
    assert extraer_antiguedad_descripcion("departamento a estrenar") == 0


def test_extraer_antiguedad_numero():
    assert extraer_antiguedad_descripcion("10 años de antigüedad aproximadamente") == 10


def test_extraer_ubicacion_referencial_avenida():
    ref = extraer_ubicacion_referencial_regex(
        "Departamento ubicado en Av. Ejercito 120, Cayma."
    )
    assert ref is not None
    assert "Av" in ref


def test_extraer_ubicacion_referencial_urbanizacion():
    ref = extraer_ubicacion_referencial_regex("Casa en Urb. Quinta Samay, cerca al parque.")
    assert ref is not None and "Urb" in ref


# -----------------------------
# Fallbacks DOM
# -----------------------------

def test_extraer_distrito_dom_desde_listado():
    assert extraer_distrito_dom("Cayma, Arequipa", DISTRITOS_NORM) == "Cayma"


def test_extraer_distrito_dom_no_reconocido():
    assert extraer_distrito_dom("Lugar Inventado, Lima", DISTRITOS_NORM) is None


def test_detectar_tipo_inmueble_fallback():
    assert detectar_tipo_inmueble_fallback(descripcion="casa grande") == "casa"
    assert detectar_tipo_inmueble_fallback(descripcion="departamento moderno") == "departamento"
    assert detectar_tipo_inmueble_fallback(descripcion="terreno de 500 m2") == "terreno"
    assert detectar_tipo_inmueble_fallback(descripcion="algo irrelevante") is None
