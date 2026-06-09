"""Tests de core/modelos/AnuncioBase."""

import pytest
from pydantic import ValidationError

from core.modelos import AnuncioBase, EstadoAnuncio


def test_anuncio_base_campos_minimos():
    a = AnuncioBase(
        enlace="https://ejemplo.com/1",
        portal="urbania",
        sector="inmobiliario",
        fecha_extraccion="2026-04-22",
    )
    assert a.enlace == "https://ejemplo.com/1"
    assert a.ausencias_consecutivas == 0
    assert a.estado_anuncio is None


def test_anuncio_base_falla_sin_enlace():
    with pytest.raises(ValidationError):
        AnuncioBase(portal="urbania", sector="inmobiliario", fecha_extraccion="2026-04-22")


def test_anuncio_base_falla_sin_fecha_extraccion():
    with pytest.raises(ValidationError):
        AnuncioBase(enlace="https://x", portal="urbania", sector="inmobiliario")


def test_estado_anuncio_enum():
    a = AnuncioBase(
        enlace="https://x",
        portal="urbania",
        sector="inmobiliario",
        fecha_extraccion="2026-04-22",
        estado_anuncio=EstadoAnuncio.NUEVO,
    )
    # use_enum_values=True → se serializa como string
    assert a.estado_anuncio == "nuevo"


def test_ausencias_no_puede_ser_negativo():
    with pytest.raises(ValidationError):
        AnuncioBase(
            enlace="https://x",
            portal="urbania",
            sector="inmobiliario",
            fecha_extraccion="2026-04-22",
            ausencias_consecutivas=-1,
        )


def test_anuncio_base_extensible():
    """Cada sector puede extender AnuncioBase con campos propios."""
    from typing import Optional

    class AnuncioEmpleoTest(AnuncioBase):
        puesto: str
        empresa: Optional[str] = None
        salario: Optional[float] = None

    a = AnuncioEmpleoTest(
        enlace="https://computrabajo.com/1",
        portal="computrabajo",
        sector="empleo",
        fecha_extraccion="2026-04-22",
        puesto="Analista Económico",
        empresa="BCRP",
    )
    assert a.puesto == "Analista Económico"
    assert a.portal == "computrabajo"
