"""Extractores IA con interfaz común. Implementación por defecto: Gemini dual-API."""

from core.extractor_ia.base import ExtractorIA
from core.extractor_ia.gemini import GeminiExtractor

__all__ = ["ExtractorIA", "GeminiExtractor"]
