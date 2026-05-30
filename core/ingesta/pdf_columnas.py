"""Lectura de PDF preservando columnas.

Aprendizaje de `INMOBILIARIA/v1-diarios`: en clasificados impresos,
PyMuPDF ordenado por bucket de columna recupero mejor los avisos que una
extraccion lineal. La dependencia se importa tarde para que el framework web
siga instalable sin extras de PDF.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


@dataclass(frozen=True)
class PaginaTexto:
    pagina: int
    texto: str


def ordenar_bloques_texto(
    blocks: Iterable[Sequence],
    *,
    ancho_columna: int = 50,
) -> list[str]:
    """Ordena bloques PyMuPDF por columna aproximada y posicion vertical."""
    bloques_texto = [b for b in blocks if len(b) >= 7 and b[6] == 0]
    bloques_texto.sort(key=lambda b: (round(float(b[0]) / ancho_columna), float(b[1])))
    return [str(b[4]) for b in bloques_texto]


def leer_pdf_columnas(
    pdf_path: str | Path,
    *,
    ancho_columna: int = 50,
    ruido_regex: re.Pattern | None = None,
) -> list[PaginaTexto]:
    """Devuelve paginas con texto ordenado por columnas.

    Requiere `pymupdf` instalado. Si no esta disponible, lanza un error claro
    en vez de romper el import del framework completo.
    """
    try:
        import fitz  # type: ignore
    except ImportError as exc:
        raise RuntimeError("leer_pdf_columnas requiere pymupdf instalado") from exc

    paginas: list[PaginaTexto] = []
    doc = fitz.open(str(pdf_path))
    try:
        for i in range(doc.page_count):
            page = doc[i]
            texto = "\n".join(
                ordenar_bloques_texto(
                    page.get_text("blocks"),
                    ancho_columna=ancho_columna,
                )
            )
            if ruido_regex:
                texto = ruido_regex.sub("", texto)
            paginas.append(PaginaTexto(pagina=i + 1, texto=texto))
    finally:
        doc.close()
    return paginas
