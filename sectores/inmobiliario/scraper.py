"""
Fachada delgada del scraper inmobiliario.

Solo abre el navegador, arma el diagnóstico estándar y rutea al módulo del
portal en `portal_scrapers/`. Toda la lógica de parseo vive en el módulo
del portal (aquí Navent), NO en esta fachada. Los tests parchean el módulo
real (`portal_scrapers.navent`), no esta fachada.
"""

import logging
from datetime import datetime

from core.browser import BrowserManager
from core.calidad import nuevo_diagnostico_scraping

from sectores.inmobiliario.config import (
    DELAY_LISTADO, DELAY_DETALLE, TIMEOUT_ELEMENTO, CARPETA_SNAPSHOTS_FRONTEND,
)
from sectores.inmobiliario.portal_scrapers import navent

logger = logging.getLogger("scraping")

_NAVENT_PORTALES = {"urbania", "adondevivir"}


def scrape_portal_con_diagnostico(
    portal: str, operacion: str, num_paginas: int, headless: bool = False,
) -> tuple[list[dict], dict]:
    """Ejecuta el scraping de un portal+operación y devuelve (datos, diagnostico)."""
    logger.info("=" * 60)
    logger.info(f"SCRAPING: {portal.upper()} - {operacion.upper()} ({num_paginas} pág.)")
    logger.info("=" * 60)

    if portal not in _NAVENT_PORTALES:
        raise ValueError(
            f"Portal '{portal}' no soportado en este ejemplo (solo Navent: "
            f"{sorted(_NAVENT_PORTALES)}). Producción vive en v1-portales-web."
        )

    diagnostico = nuevo_diagnostico_scraping(portal, operacion, "navent")
    browser = BrowserManager(
        headless=headless,
        delay_listado=DELAY_LISTADO,
        delay_detalle=DELAY_DETALLE,
        timeout_elemento=TIMEOUT_ELEMENTO,
    )
    fecha_extraccion = datetime.now().strftime("%Y-%m-%d")

    try:
        resultados = navent.scrape_listados(
            browser, portal, operacion, num_paginas,
            diagnostico=diagnostico,
            carpeta_snapshots=CARPETA_SNAPSHOTS_FRONTEND,
        )
        for r in resultados:
            r["portal"] = portal
            r["tipo_operacion"] = operacion
            r["fecha_extraccion"] = fecha_extraccion
        logger.info(f"Scraping completado: {len(resultados)} anuncios")
        return resultados, diagnostico
    finally:
        browser.cerrar()
