"""Contrato común de un scraper de portal (sector-agnóstico).

Formaliza la política **HTTP-first** como un contrato tipado: cada portal
declara su `cliente_preferido` y separa el descubrimiento del listado de la
extracción del detalle. Esto hace explícita, en el código, la decisión de
transporte que antes solo vivía en la documentación.

`PortalScraper` es un `Protocol` (tipado estructural): un portal NO necesita
heredar de él — basta con que tenga los atributos y métodos correctos. Así el
contrato no acopla a los sectores con `core/` por herencia.

Patrón de uso en el orquestador de un sector::

    def correr(portal: PortalScraper, operacion: str, *, historial, ...):
        refs = portal.descubrir_listado(operacion)        # barato
        nuevas = [r for r in refs if r.enlace not in conocidas]
        anuncios = [d for r in nuevas if (d := portal.extraer_detalle(r))]
        ...

`cliente_preferido` documenta y permite ramificar la estrategia de transporte:

- ``"http"``    → `core.http.HttpClient` (default; sin navegador).
- ``"browser"`` → `core.browser` (solo si hay anti-bot confirmado o JS pesado).
- ``"hybrid"``  → listado por HTTP, detalle por navegador (o viceversa).
"""

from __future__ import annotations

from typing import Literal, Protocol, Sequence, runtime_checkable

from core.modelos import AnuncioBase, RefAnuncio

ClientePreferido = Literal["http", "browser", "hybrid"]


@runtime_checkable
class PortalScraper(Protocol):
    """Lo que cualquier scraper de portal debe exponer.

    Atributos:
        fuente: identificador del portal (p. ej. ``"urbania"``).
        cliente_preferido: transporte declarado (ver módulo). Sirve de
            documentación viva y permite al orquestador elegir cliente.
    """

    fuente: str
    cliente_preferido: ClientePreferido

    def descubrir_listado(self, operacion: str | None) -> Sequence[RefAnuncio]:
        """Devuelve las referencias (IDs/URLs) visibles en el listado.

        Paso barato: NO descarga el detalle de cada anuncio. `operacion` es el
        alcance consultado (región, tipo de operación, rubro…); None si el
        sector no usa operaciones.
        """
        ...

    def extraer_detalle(self, ref: RefAnuncio) -> AnuncioBase | None:
        """Descarga y parsea el detalle de una referencia.

        Devuelve None si el anuncio no se pudo extraer (el orquestador lo
        cuenta como error parcial, no aborta la corrida).
        """
        ...


__all__ = ["ClientePreferido", "PortalScraper"]
