"""Diagnóstico estructurado de una corrida de scraping.

Patrón heredado de v1: cada scraper de portal devuelve un dict con
campos estándar (`paginas_visitadas`, `tarjetas_totales`, etc.) que la
compuerta de calidad y el reporte de mantenimiento consumen sin tener
que conocer las particularidades de cada portal.

Si dos portales devuelven `diagnostico` con shapes distintos, todo
lo que viene después (compuerta, reportes, logs comparables) se rompe.
Por eso esta función es el constructor único.

Campos opcionales por estrategia:

* Para SPAs Next.js / Redux (Navent, etc.) se agregan
  `redux_paginas_ok`, `redux_paginas_fallidas`, `postings_redux_totales`,
  `postings_matcheados`, `ratio_match_redux_dom`.
* Para portales que dependen de un segundo pase a detalle
  (Properati, REMAX en v1) los contadores `detalle_intentos` /
  `detalle_exitos` permiten saber cuánta descripción se perdió.
"""

from __future__ import annotations

from typing import Any


def nuevo_diagnostico_scraping(
    portal: str,
    operacion: str | None,
    estrategia: str,
) -> dict[str, Any]:
    """Diagnóstico base con todas las claves estándar inicializadas.

    `estrategia` es un identificador libre del modo de scraping del
    portal (`navent`, `properati`, `remax`, `requests_html`, etc.). Lo
    usan los umbrales de calidad (`UMBRALES_CALIDAD[estrategia]`) y los
    mapas del reporte de mantenimiento (`_CODIGO_POR_PORTAL`/equivalente).
    """
    return {
        "portal": portal,
        "operacion": operacion,
        "estrategia": estrategia,
        "paginas_visitadas": 0,
        "paginas_con_tarjetas": 0,
        "paginas_sin_tarjetas": 0,
        "tarjetas_totales": 0,
        "detalle_intentos": 0,
        "detalle_exitos": 0,
        # Específicos de SPAs Next.js. Se dejan inicializados aunque el
        # portal no sea Redux-based — comparar contra 0 es siempre seguro.
        "redux_requerido": estrategia == "navent",
        "redux_paginas_ok": 0,
        "redux_paginas_fallidas": 0,
        "postings_redux_totales": 0,
        "postings_matcheados": 0,
        "ratio_match_redux_dom": None,
        # Para auditoría y handoff con la IA de mantenimiento.
        "motivos_degradacion": [],
        "snapshots_html": [],
    }
