"""Ingesta de fuentes documentales para scrapers no web puros."""

from core.ingesta.pdf_columnas import PaginaTexto, leer_pdf_columnas, ordenar_bloques_texto
from core.ingesta.pdf_tablas import (
    Palabra,
    TablaExtraida,
    agrupar_en_filas,
    detectar_cortes_columnas,
    extraer_tablas_pdf,
    reconstruir_tabla,
)
from core.ingesta.segmentacion import AvisoCrudo, segmentar_documento, segmentar_pagina

__all__ = [
    "AvisoCrudo",
    "PaginaTexto",
    "Palabra",
    "TablaExtraida",
    "agrupar_en_filas",
    "detectar_cortes_columnas",
    "extraer_tablas_pdf",
    "leer_pdf_columnas",
    "ordenar_bloques_texto",
    "reconstruir_tabla",
    "segmentar_documento",
    "segmentar_pagina",
]
