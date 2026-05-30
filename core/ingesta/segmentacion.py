"""Segmentacion de textos documentales por codigos de aviso."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from core.ingesta.pdf_columnas import PaginaTexto


@dataclass(frozen=True)
class AvisoCrudo:
    codigo: str
    seccion: str | None
    texto: str
    pagina: int


def _normalizar_seccion(codigo: str, seccion_regex: re.Pattern | None) -> str | None:
    if not seccion_regex:
        return None
    match = seccion_regex.search(codigo)
    if not match:
        return None
    return re.sub(r"[-\s]", "", "".join(match.groups()).upper())


def segmentar_pagina(
    texto: str,
    *,
    pagina: int,
    codigo_regex: re.Pattern,
    seccion_regex: re.Pattern | None = None,
    secciones_objetivo: set[str] | None = None,
    recortar_ruido: bool = True,
) -> list[AvisoCrudo]:
    """Segmenta una pagina tomando el codigo al final de cada aviso."""
    avisos: list[AvisoCrudo] = []
    cursor = 0
    for match in codigo_regex.finditer(texto):
        codigo = match.group(1).strip()
        seccion = _normalizar_seccion(codigo, seccion_regex)
        descripcion = texto[cursor:match.start()].strip()
        cursor = match.end()
        if not descripcion:
            continue
        if secciones_objetivo and seccion not in secciones_objetivo:
            continue
        if recortar_ruido and len(descripcion) > 600:
            partes = re.split(r"\n{2,}", descripcion)
            descripcion = partes[-1].strip() if partes else descripcion
        avisos.append(
            AvisoCrudo(codigo=codigo, seccion=seccion, texto=descripcion, pagina=pagina)
        )
    return avisos


def segmentar_documento(
    paginas: Iterable[PaginaTexto | tuple[int, str]],
    *,
    codigo_regex: re.Pattern,
    seccion_regex: re.Pattern | None = None,
    secciones_objetivo: set[str] | None = None,
) -> list[AvisoCrudo]:
    """Segmenta todas las paginas y filtra por secciones si corresponde."""
    todos: list[AvisoCrudo] = []
    for item in paginas:
        if isinstance(item, PaginaTexto):
            pagina, texto = item.pagina, item.texto
        else:
            pagina, texto = item
        todos.extend(
            segmentar_pagina(
                texto,
                pagina=pagina,
                codigo_regex=codigo_regex,
                seccion_regex=seccion_regex,
                secciones_objetivo=secciones_objetivo,
            )
        )
    return todos
