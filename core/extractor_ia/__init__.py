"""Extractores IA con interfaz comun. Implementacion por defecto: DeepSeek."""

from core.extractor_ia.base import ExtractorIA
from core.extractor_ia.deepseek import DeepSeekExtractor

__all__ = ["ExtractorIA", "DeepSeekExtractor"]
