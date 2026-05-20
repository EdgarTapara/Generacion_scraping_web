"""Pipeline de limpieza para el sector <SECTOR>.

Patrón:
    datos_crudos (list[dict] del scraper) → DataFrame validado y normalizado.

Usa helpers genéricos de `core.limpieza` para precios/fechas/monedas y
añade los regex y fallbacks específicos del sector.
"""

from __future__ import annotations

import logging
from datetime import datetime

import pandas as pd

from core.limpieza import (
    parsear_numero,
    parsear_entero,
    moneda_a_iso,
    limpiar_precio_pe,
    limpiar_fecha_relativa,
)

logger = logging.getLogger("scraping")


def pipeline_limpieza(
    datos_crudos: list[dict],
    portal: str,
    operacion: str | None = None,
) -> pd.DataFrame:
    """Toma los dict crudos del scraper y devuelve un DataFrame limpio."""
    if not datos_crudos:
        return pd.DataFrame()

    filas: list[dict] = []
    for crudo in datos_crudos:
        fila = _limpiar_fila(crudo, portal, operacion)
        if fila:
            filas.append(fila)

    if not filas:
        return pd.DataFrame()

    df = pd.DataFrame(filas)
    df["fecha_extraccion"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    df["portal"] = portal
    if operacion is not None:
        df["tipo_operacion"] = operacion
    return df


def _limpiar_fila(crudo: dict, portal: str, operacion: str | None) -> dict | None:
    """Aplica limpieza por campo + fallbacks en cascada (Redux → DOM → regex)."""
    # TODO: implementar según campos del sector.
    # Patrón típico:
    #
    # if not crudo.get("enlace"):
    #     return None
    #
    # precio_data = limpiar_precio_pe(crudo.get("precio_raw"))
    # fecha = limpiar_fecha_relativa(crudo.get("fecha_publicacion_raw"))
    #
    # return {
    #     "enlace": crudo["enlace"],
    #     "precio": precio_data["precio"],
    #     "moneda": precio_data["moneda"],
    #     "fecha_publicacion": fecha,
    #     ...
    # }
    raise NotImplementedError
