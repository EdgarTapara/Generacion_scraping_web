"""Helpers compartidos por los scrapers de portales del sector <SECTOR>.

Cosas que SÍ van acá:
    - Normalizaciones de campos específicas del sector (mapeo de
      taxonomías propias, parseo de un formato peculiar del rubro).
    - Selectores comunes a varios portales hermanos (Urbania y
      AdondeVivir comparten esquema Navent).

Cosas que NO van acá (porque ya viven en `core/`):
    - `nuevo_diagnostico_scraping` → `core.calidad`
    - `guardar_snapshot_html` → `core.snapshots`
    - `parsear_numero`, `moneda_a_iso`, `limpiar_precio_pe` → `core.limpieza`
    - `BrowserManager` → `core.browser`
"""

from __future__ import annotations

import logging

logger = logging.getLogger("scraping")


# TODO: agregar acá helpers que más de un portal del sector usen.
# Ejemplo (sector empleo, si Computrabajo y Bumeran comparten el mismo
# parseo de "Hace 3 días" pero con su propio prefijo):
#
# def parsear_publicacion_<sector>(texto: str | None) -> str | None:
#     ...
