"""Utilidades transversales: normalización de enlaces, texto y hashing.

Estos helpers existen porque ya aparecieron en al menos dos lugares del
pipeline (historial SQLite y cache de extractor IA). Centralizar la
implementación garantiza que dos subsistemas que se comparan por clave
generen la misma representación canónica byte a byte.
"""

from core.utils.enlaces import normalizar_enlace, hash_enlace
from core.utils.texto import (
    normalizar_texto,
    normalizar_para_hash,
    descripcion_hash,
)
from core.utils.identidad import publicacion_id, asignar_publicacion_id

__all__ = [
    "normalizar_enlace",
    "hash_enlace",
    "normalizar_texto",
    "normalizar_para_hash",
    "descripcion_hash",
    "publicacion_id",
    "asignar_publicacion_id",
]
