"""Scraper del portal A — patrón modular validado en v1 inmobiliario.

Convenciones:
    * Función pública: `scrape_listados_portal_a(browser, operacion, num_paginas,
                                                 diagnostico=None) -> list[dict]`
      Devuelve los registros crudos. El diagnóstico se modifica in-place
      (si el caller lo pasó).
    * Si el portal es SPA Next.js → priorizar `__NEXT_DATA__` con
      `core.redux.extraer_redux_state`.
    * En CADA página visitada llamar `guardar_snapshot_html(...)` para que
      una eventual corrida degradada deje evidencia.
    * Actualizar contadores del diagnóstico: `paginas_visitadas`,
      `paginas_con_tarjetas`, `tarjetas_totales`, etc.
"""

from __future__ import annotations

import logging
from typing import Any

from selenium.webdriver.common.by import By

from core.browser import BrowserManager, buscar_texto_rapido
from core.calidad import nuevo_diagnostico_scraping
from core.redux import extraer_next_data, buscar_clave_recursivo
from core.snapshots import guardar_snapshot_html

logger = logging.getLogger("scraping")


def scrape_listados_portal_a(
    browser: BrowserManager,
    operacion: str | None,
    num_paginas: int,
    diagnostico: dict[str, Any] | None = None,
) -> list[dict]:
    """TODO: implementar.

    Patrón de referencia (de v1 inmobiliario, navent.py):

        from sectores.<mi_sector> import config

        if diagnostico is None:
            diagnostico = nuevo_diagnostico_scraping("portal_a", operacion, "navent")

        resultados: list[dict] = []
        for pagina in range(1, num_paginas + 1):
            diagnostico["paginas_visitadas"] += 1
            url = config.generar_url_listado("portal_a", operacion, pagina)
            driver = browser.navegar(url, tipo="listado")
            guardar_snapshot_html(
                driver, "portal_a", operacion, pagina, "listado",
                carpeta_snapshots=config.CARPETA_SNAPSHOTS_FRONTEND,
                diagnostico=diagnostico,
            )

            # Fuente primaria: Redux / __NEXT_DATA__
            blob = extraer_next_data(driver.page_source)
            postings = buscar_clave_recursivo(blob, "listPostings") if blob else None

            if postings:
                diagnostico["redux_paginas_ok"] += 1
                diagnostico["postings_redux_totales"] += len(postings)
                # ... parsear postings y appendear a resultados
            else:
                # Fallback DOM
                diagnostico["redux_paginas_fallidas"] += 1
                tarjetas = driver.find_elements(By.CSS_SELECTOR, '[data-qa="<selector>"]')
                if tarjetas:
                    diagnostico["paginas_con_tarjetas"] += 1
                    diagnostico["tarjetas_totales"] += len(tarjetas)
                else:
                    diagnostico["paginas_sin_tarjetas"] += 1
                # ... parsear tarjetas

        return resultados
    """
    raise NotImplementedError
