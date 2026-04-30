"""Tests de AnuncioInmobiliario — hereda AnuncioBase y añade reglas propias."""

import pytest
from pydantic import ValidationError

from sectores.inmobiliario.modelos import (
    AnuncioInmobiliario, DISTRITOS_NORM, validar_anuncio,
)


def test_hereda_campos_de_anuncio_base():
    a = AnuncioInmobiliario(
        enlace="https://urbania.pe/1",
        portal="urbania",
        fecha_extraccion="2026-04-22",
        tipo_operacion="alquiler",
    )
    # `sector` default = "inmobiliario"
    assert a.sector == "inmobiliario"
    assert a.tipo_operacion == "alquiler"
    assert a.ausencias_consecutivas == 0


def test_moneda_restringida_a_pen_usd():
    with pytest.raises(ValidationError):
        AnuncioInmobiliario(
            enlace="https://x", portal="x", fecha_extraccion="2026-04-22",
            tipo_operacion="alquiler", moneda="EUR",
        )


def test_precio_negativo_rechazado():
    with pytest.raises(ValidationError):
        AnuncioInmobiliario(
            enlace="https://x", portal="x", fecha_extraccion="2026-04-22",
            tipo_operacion="alquiler", precio=-100.0,
        )


def test_area_fuera_de_rango_rechazada():
    with pytest.raises(ValidationError):
        AnuncioInmobiliario(
            enlace="https://x", portal="x", fecha_extraccion="2026-04-22",
            tipo_operacion="alquiler", area_total_m2=999999.0,
        )


def test_distritos_arequipa_catalogo_completo():
    # Sanity: los distritos clave están en el catálogo normalizado
    for d in ("cayma", "yanahuara", "cerro colorado", "miraflores"):
        assert d in DISTRITOS_NORM


def test_validar_anuncio_warn_precio_fuera_de_rango():
    a = AnuncioInmobiliario(
        enlace="https://x", portal="x", fecha_extraccion="2026-04-22",
        tipo_operacion="alquiler",
        precio=50.0, moneda="PEN",  # < S/ 150 mínimo
        distrito="Cayma", titulo="Alquiler apartamento Cayma S/ 50",
    )
    warnings = validar_anuncio(a)
    assert any("fuera de rango" in w for w in warnings)


def test_validar_anuncio_warn_distrito_desconocido():
    a = AnuncioInmobiliario(
        enlace="https://x", portal="x", fecha_extraccion="2026-04-22",
        tipo_operacion="alquiler",
        distrito="Ciudad Inexistente", titulo="Alquiler apartamento X S/ 1000",
        precio=1000.0, moneda="PEN",
    )
    warnings = validar_anuncio(a)
    assert any("Distrito no reconocido" in w for w in warnings)
