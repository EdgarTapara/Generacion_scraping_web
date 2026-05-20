"""Normalización de texto y hashing para deduplicación semántica.

`descripcion_hash` es el truco que permite no quemar tokens de DeepSeek
cuando un portal reedita un anuncio sin cambiar contenido relevante.
Espacios, saltos de línea, mayúsculas y puntuación no deben generar un
hash distinto.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata

import pandas as pd

_RE_WHITESPACE = re.compile(r"\s+")


def normalizar_texto(valor: object) -> str:
    """Lowercase + sin tildes + colapsa espacios. Tolera NaN de pandas."""
    if valor is None:
        return ""
    try:
        if pd.isna(valor):
            return ""
    except (TypeError, ValueError):
        pass
    texto = str(valor).strip().lower()
    if not texto:
        return ""
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = _RE_WHITESPACE.sub(" ", texto)
    return texto.strip()


def normalizar_para_hash(texto: str | None) -> str:
    """Versión agresiva: lowercase + colapsa espacios. Conserva acentos.

    No quitamos acentos aquí porque "más" y "mas" pueden ser palabras
    distintas y los modelos las interpretan diferente. Para comparar
    descripciones por contenido nos basta con normalizar whitespace.
    """
    if texto is None:
        return ""
    try:
        if pd.isna(texto):
            return ""
    except (TypeError, ValueError):
        pass
    s = str(texto).strip()
    if not s:
        return ""
    return _RE_WHITESPACE.sub(" ", s.lower()).strip()


def descripcion_hash(descripcion: str | None) -> str:
    """SHA256 del texto normalizado para identificar reescrituras superficiales.

    Dos descripciones que difieren sólo en whitespace o capitalización
    deben mapear al mismo hash y reusar cache IA. Esto evita gastar
    tokens cuando el portal reedita el anuncio sin cambiar contenido.
    """
    canonico = normalizar_para_hash(descripcion)
    return hashlib.sha256(canonico.encode("utf-8")).hexdigest()
