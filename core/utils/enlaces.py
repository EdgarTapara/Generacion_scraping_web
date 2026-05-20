"""Normalización canónica de URLs.

Toda comparación de identidad (historial SQLite, cache IA, deduplicación
del Excel acumulativo) DEBE pasar por `normalizar_enlace`. Si dos
subsistemas usan formas distintas (uno con query string, otro sin él),
los hits de cache no coinciden y se reprocesa innecesariamente.
"""

from __future__ import annotations

import hashlib
from urllib.parse import urlparse, urlunparse


def normalizar_enlace(enlace: str | None) -> str:
    """Devuelve la URL sin query ni fragmento y sin slash final.

    Centralizado para que historial SQLite (clave primaria por sector +
    portal + enlace) y cache IA (clave por publicación) coincidan byte
    a byte. No intentamos normalizar netloc (www vs no-www) porque
    perderíamos información si un portal expone dos hosts distintos.
    """
    if not enlace or not isinstance(enlace, str):
        return ""
    p = urlparse(enlace.strip())
    limpio = urlunparse((p.scheme, p.netloc, p.path, "", "", ""))
    return limpio.rstrip("/")


def hash_enlace(enlace: str | None, longitud: int = 16) -> str:
    """SHA1 truncado del enlace canónico. Útil como fallback de id estable."""
    canonico = normalizar_enlace(enlace)
    return hashlib.sha1(canonico.encode("utf-8")).hexdigest()[:longitud]
