"""
Dispatcher del scraper inmobiliario — elige la estrategia según el portal.

El trabajo pesado vive en `portales/*.py`. Este módulo solo:
  - Abre un BrowserManager (una sola instancia de Chrome por corrida).
  - Enruta al scraper del portal correcto.
  - Inyecta metadatos comunes (portal, tipo_operacion, fecha_extraccion).
"""

import logging
from datetime import datetime

from core.browser import BrowserManager

from sectores.inmobiliario.config import (
    DELAY_LISTADO, DELAY_DETALLE, TIMEOUT_ELEMENTO,
)
from sectores.inmobiliario.portales import navent, properati, remax

logger = logging.getLogger("scraping")


def scrape_portal(
    portal: str, operacion: str, num_paginas: int, headless: bool = False,
) -> list[dict]:
    """Ejecuta scraping completo de un portal+operación."""
    logger.info("=" * 60)
    logger.info(f"SCRAPING: {portal.upper()} - {operacion.upper()}")
    logger.info(f"Paginas: {num_paginas}")
    logger.info("=" * 60)

    browser = BrowserManager(
        headless=headless,
        delay_listado=DELAY_LISTADO,
        delay_detalle=DELAY_DETALLE,
        timeout_elemento=TIMEOUT_ELEMENTO,
    )
    fecha_extraccion = datetime.now().strftime("%Y-%m-%d")

    try:
        logger.info("Extrayendo datos de paginas de listado...")

        if portal in ("urbania", "adondevivir"):
            resultados = navent.scrape_listados(browser, portal, operacion, num_paginas)
        elif portal == "properati":
            resultados = properati.scrape_listados(browser, operacion, num_paginas)
        elif portal == "remax":
            resultados = remax.scrape_listados(browser, operacion, num_paginas)
        else:
            raise ValueError(f"Portal no soportado: {portal}")

        if not resultados:
            logger.warning("No se encontraron anuncios. Abortando.")
            return []

        # Metadatos comunes por registro
        for r in resultados:
            r["portal"] = portal
            r["tipo_operacion"] = operacion
            r["fecha_extraccion"] = fecha_extraccion

        logger.info(f"Scraping completado: {len(resultados)} anuncios extraidos")
        return resultados
    finally:
        browser.cerrar()
