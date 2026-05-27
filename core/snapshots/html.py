"""Guardado de HTML renderizado de una página visitada por Selenium.

El sector decide la carpeta destino. Convención v1:
    `<sector>/resultados/snapshots_frontend/<portal>_<op>_p01_listado_YYYYMMDD_HHMMSS.html`
"""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("scraping")


def _slug_seguro(valor: str | None) -> str:
    """Reemplaza todo lo que no sea [a-z0-9_-] por '_'. Output siempre no vacío."""
    texto = str(valor or "").strip().lower()
    texto = re.sub(r"[^a-z0-9_-]+", "_", texto)
    return texto.strip("_") or "sin_valor"


def guardar_snapshot_html(
    driver,
    portal: str,
    operacion: str | None,
    pagina: int,
    etapa: str,
    carpeta_snapshots: str | os.PathLike[str],
    diagnostico: dict[str, Any] | None = None,
) -> str | None:
    """Guarda HTML renderizado y lo registra en `diagnostico["snapshots_html"]`.

    Parámetros:
        driver: webdriver Selenium ya navegado.
        portal, operacion, pagina, etapa: identifican el contexto. `etapa`
            es libre (`listado`, `detalle`, `fallback_dom`, etc.).
        carpeta_snapshots: directorio donde se guardan los .html. Se crea
            si no existe.
        diagnostico: dict que devolvió `nuevo_diagnostico_scraping`. Si se
            pasa, se le hace append a la lista `snapshots_html` con info
            del archivo (archivo, url, titulo, bytes).

    Retorna la ruta absoluta del archivo o None si falló (no rompe la corrida).
    Best-effort: cualquier excepción se loguea y se devuelve None.
    """
    try:
        html = driver.page_source or ""
    except Exception as e:
        logger.debug("No se pudo leer page_source para snapshot: %s", e)
        return None

    if not html.strip():
        return None

    carpeta = Path(carpeta_snapshots)
    try:
        carpeta.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.warning("No se pudo crear carpeta snapshots %s: %s", carpeta, e)
        return None

    sello = datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre = (
        f"{_slug_seguro(portal)}_{_slug_seguro(operacion)}_"
        f"p{int(pagina):02d}_{_slug_seguro(etapa)}_{sello}.html"
    )
    ruta = carpeta / nombre

    try:
        ruta.write_text(html, encoding="utf-8")
    except Exception as e:
        logger.warning(
            "No se pudo guardar snapshot HTML %s/%s p%s: %s",
            portal, operacion, pagina, e,
        )
        return None

    try:
        titulo = driver.title
    except Exception:
        titulo = ""
    try:
        url_actual = driver.current_url
    except Exception:
        url_actual = ""

    if diagnostico is not None:
        diagnostico.setdefault("snapshots_html", []).append({
            "archivo": str(ruta),
            "portal": portal,
            "operacion": operacion,
            "pagina": pagina,
            "etapa": etapa,
            "url": url_actual,
            "titulo": titulo,
            "bytes": ruta.stat().st_size,
        })

    logger.info("  Snapshot HTML guardado: %s", ruta)
    return str(ruta)
