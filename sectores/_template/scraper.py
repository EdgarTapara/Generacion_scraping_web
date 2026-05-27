"""Dispatcher del sector <SECTOR> — fachada delgada.

Patrón v1 inmobiliario: este archivo SOLO rutea. La lógica de cada
portal vive en `portal_scrapers/<portal>.py`. Si tu cambio es de
selectores o parser, NO toques este archivo; editá el módulo del
portal afectado.

API estable (no romper sin migración):
    `scrape_portal_con_diagnostico(portal, operacion, num_paginas, headless)
       -> (list[dict], dict)`
"""

from __future__ import annotations

import logging
from datetime import datetime

from core.browser import BrowserManager
from core.calidad import nuevo_diagnostico_scraping

logger = logging.getLogger("scraping")


def scrape_portal_con_diagnostico(
    portal: str,
    operacion: str | None,
    num_paginas: int,
    headless: bool = False,
) -> tuple[list[dict], dict]:
    """Punto de entrada. Devuelve (resultados, diagnostico)."""
    from sectores._template import config  # TODO: reemplazar al copiar

    browser = BrowserManager(
        headless=headless,
        delay_listado=config.DELAY_LISTADO,
        delay_detalle=config.DELAY_DETALLE,
        timeout_elemento=config.TIMEOUT_ELEMENTO,
    )
    fecha_extraccion = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        if portal == "portal_a":
            from sectores._template.portal_scrapers.portal_a import scrape_listados_portal_a  # TODO renombrar
            diagnostico = nuevo_diagnostico_scraping(portal, operacion, "<estrategia>")
            resultados = scrape_listados_portal_a(
                browser, operacion, num_paginas, diagnostico=diagnostico
            )
        # elif portal == "portal_b":
        #     ...
        else:
            raise ValueError(f"Portal no soportado: {portal}")

        for r in resultados:
            r["portal"] = portal
            if operacion is not None:
                r["tipo_operacion"] = operacion
            r["fecha_extraccion"] = fecha_extraccion

        return resultados, diagnostico
    finally:
        browser.cerrar()
