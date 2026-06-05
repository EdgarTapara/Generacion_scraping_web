"""Scraper del portal A — patrón modular validado en v1 inmobiliario.

DECISIÓN PREVIA — transporte HTTP-first (ver AGENTS.md):
    NO uses navegador por default. Probá en orden:
      1. API / JSON / XHR → `core.http.HttpClient`.
      2. HTML server-side → `core.http` + parser (BeautifulSoup / JSON-LD).
      3. SPA Next.js → `core.redux.extraer_next_data(html)` SIN navegador.
      4. Sólo si nada alcanza, o `detectar_bloqueo_anti_bot` confirma un
         desafío → `core.browser.BrowserManager`.
    Este template muestra el camino con navegador; si tu portal es HTTP,
    el primer parámetro es un `HttpClient` en vez de un `BrowserManager`.

Convenciones:
    * Función pública: `scrape_listados_portal_a(cliente, operacion, num_paginas,
                                                 diagnostico=None) -> list[dict]`
      donde `cliente` es un `HttpClient` (HTTP-first) o un `BrowserManager`.
      Devuelve los registros crudos. El diagnóstico se modifica in-place.
    * Si usás `core.http`: ante cada respuesta corré
      `detectar_bloqueo_anti_bot(r.status_code, r.text)` y, si dispara,
      guardá el motivo en `diagnostico["anti_bot"]` (el reporte lo escala).
    * En CADA página visitada llamar `guardar_snapshot_html(...)` (o guardar
      el HTML/JSON crudo) para que una corrida degradada deje evidencia.
    * Actualizar contadores del diagnóstico: `paginas_visitadas`,
      `paginas_con_tarjetas`, `tarjetas_totales`, etc.
"""

from __future__ import annotations

import logging
from typing import Any

from selenium.webdriver.common.by import By

from core.browser import BrowserManager, buscar_texto_rapido
from core.calidad import nuevo_diagnostico_scraping
from core.contratos import ClientePreferido  # contrato HTTP-first
from core.http import HttpClient, detectar_bloqueo_anti_bot  # HTTP-first (preferido)
from core.redux import extraer_next_data, buscar_clave_recursivo
from core.snapshots import guardar_snapshot_html

logger = logging.getLogger("scraping")

# Declará el transporte de este portal (ver core.contratos.PortalScraper).
# "http" es el default sano; subí a "browser"/"hybrid" SÓLO si lo necesitás.
FUENTE = "portal_a"
CLIENTE_PREFERIDO: ClientePreferido = "http"


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
