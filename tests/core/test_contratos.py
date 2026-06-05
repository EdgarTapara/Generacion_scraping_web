"""Tests del contrato `core.contratos.PortalScraper`."""

from datetime import datetime

from core.contratos import PortalScraper
from core.modelos import AnuncioBase, RefAnuncio


class _PortalFalso:
    """Implementa el contrato por tipado estructural, sin heredar nada."""

    fuente = "demo"
    cliente_preferido = "http"

    def descubrir_listado(self, operacion):
        return [RefAnuncio(enlace="https://demo/1", fuente="demo", operacion=operacion)]

    def extraer_detalle(self, ref):
        return AnuncioBase(
            enlace=ref.enlace,
            portal="demo",
            sector="test",
            fecha_extraccion=datetime.now().isoformat(),
        )


def test_portal_cumple_protocolo_estructuralmente():
    portal = _PortalFalso()
    assert isinstance(portal, PortalScraper)


def test_objeto_incompleto_no_cumple_protocolo():
    class _Incompleto:
        fuente = "x"
        # falta cliente_preferido, descubrir_listado, extraer_detalle

    assert not isinstance(_Incompleto(), PortalScraper)


def test_flujo_listado_detalle():
    portal = _PortalFalso()
    refs = portal.descubrir_listado("alquiler")
    assert refs[0].operacion == "alquiler"
    anuncio = portal.extraer_detalle(refs[0])
    assert anuncio is not None
    assert anuncio.enlace == "https://demo/1"


def test_refanuncio_es_inmutable():
    ref = RefAnuncio(enlace="https://demo/1", fuente="demo")
    try:
        ref.enlace = "otro"
    except Exception:
        return
    raise AssertionError("RefAnuncio deberia ser frozen")
