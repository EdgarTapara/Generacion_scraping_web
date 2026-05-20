"""Scraper del sector <SECTOR>: orquesta los portales declarados.

Patrón (v1-validado):
    1. Para cada página: navegar al listado, extraer tarjetas.
    2. Para cada tarjeta: extraer campos directos + URL detalle.
    3. (Opcional) Segundo pase a páginas de detalle para descripción.
    4. Devolver (datos_crudos: list[dict], diagnostico: dict).

El diagnóstico es **clave** para la compuerta de calidad: contiene
métricas como `paginas_visitadas`, `tarjetas_totales`, `redux_paginas_ok`,
`ratio_match_redux_dom`, etc.
"""

from __future__ import annotations

import logging
from typing import Any

from core.browser import BrowserManager

logger = logging.getLogger("scraping")


def scrape_portal_con_diagnostico(
    portal: str,
    operacion: str | None,
    num_paginas: int,
    headless: bool = False,
) -> tuple[list[dict], dict[str, Any]]:
    """Punto de entrada. Devuelve (datos_crudos, diagnostico)."""
    # TODO: implementar el ruteo por portal. Patrón:
    #
    # browser = BrowserManager(
    #     headless=headless,
    #     delay_listado=config.DELAY_LISTADO,
    #     delay_detalle=config.DELAY_DETALLE,
    #     timeout_elemento=config.TIMEOUT_ELEMENTO,
    # )
    # try:
    #     if portal == "portal_a":
    #         from sectores.<mi_sector>.portales.portal_a import scrape_portal_a
    #         return scrape_portal_a(browser, operacion, num_paginas)
    #     elif portal == "portal_b":
    #         from sectores.<mi_sector>.portales.portal_b import scrape_portal_b
    #         return scrape_portal_b(browser, operacion, num_paginas)
    #     else:
    #         raise ValueError(f"Portal no soportado: {portal}")
    # finally:
    #     browser.cerrar()
    raise NotImplementedError
