"""Scraper del portal A.

Patrón:
    * Si el portal es SPA con Next.js → priorizar __NEXT_DATA__ vía
      `core.redux.extraer_redux_state`. Más resiliente a cambios de UI.
    * Si es HTML server-side → selectores estables (data-test, data-qa).
    * Siempre incluir un fallback regex sobre DOM cuando la fuente
      primaria falle, registrando la pérdida en el diagnóstico.

Devuelve (datos_crudos, diagnostico). datos_crudos es list[dict] con los
campos que después leerá `limpieza.py`.
"""

from __future__ import annotations

import logging
from typing import Any

from selenium.webdriver.common.by import By

from core.browser import BrowserManager, buscar_texto_rapido
from core.redux import extraer_redux_state

logger = logging.getLogger("scraping")


def scrape_portal_a(
    browser: BrowserManager,
    operacion: str | None,
    num_paginas: int,
) -> tuple[list[dict], dict[str, Any]]:
    """TODO: implementar. Patrón de Navent (Urbania, AdondeVivir) en v1."""
    datos: list[dict] = []
    diag: dict[str, Any] = {
        "portal": "portal_a",
        "operacion": operacion,
        "estrategia": "<navent|properati|remax|requests|custom>",
        "paginas_visitadas": 0,
        "paginas_con_tarjetas": 0,
        "tarjetas_totales": 0,
        # Si el portal es SPA Next.js, agregar:
        # "redux_paginas_ok": 0,
        # "redux_paginas_fallidas": 0,
        # "ratio_match_redux_dom": None,
    }

    # for pagina in range(1, num_paginas + 1):
    #     url = config.generar_url_listado("portal_a", operacion, pagina)
    #     driver = browser.navegar(url, tipo="listado")
    #     diag["paginas_visitadas"] += 1
    #
    #     html = driver.page_source
    #     estado = extraer_redux_state(html, ["listPostings", "postings"])
    #     if estado:
    #         # 1. Parser primario: Redux
    #         postings = estado.get("listPostings") or estado.get("postings")
    #         diag["redux_paginas_ok"] = diag.get("redux_paginas_ok", 0) + 1
    #         for p in postings:
    #             datos.append({...})
    #     else:
    #         # 2. Fallback DOM
    #         diag["redux_paginas_fallidas"] = diag.get("redux_paginas_fallidas", 0) + 1
    #         tarjetas = driver.find_elements(By.CSS_SELECTOR, "<selector>")
    #         for t in tarjetas:
    #             datos.append({...})

    return datos, diag
