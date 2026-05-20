"""Extractores IA con interfaz comun. Implementacion por defecto: DeepSeek.

Incluye también la capa de cache `CachePublicaciones` que indexa respuestas
por (publicacion_id, descripcion_hash, campo). Esa capa es la diferencia
entre quemar tokens en cada corrida o sólo pagar por contenido nuevo.
"""

from core.extractor_ia.base import ExtractorIA
from core.extractor_ia.cache import CachePublicaciones
from core.extractor_ia.deepseek import DeepSeekExtractor

__all__ = ["ExtractorIA", "DeepSeekExtractor", "CachePublicaciones"]
