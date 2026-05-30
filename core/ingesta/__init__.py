"""Ingesta de fuentes documentales para scrapers no web puros."""

from core.ingesta.pdf_columnas import PaginaTexto, leer_pdf_columnas, ordenar_bloques_texto
from core.ingesta.segmentacion import AvisoCrudo, segmentar_documento, segmentar_pagina

__all__ = [
    "AvisoCrudo",
    "PaginaTexto",
    "leer_pdf_columnas",
    "ordenar_bloques_texto",
    "segmentar_documento",
    "segmentar_pagina",
]
