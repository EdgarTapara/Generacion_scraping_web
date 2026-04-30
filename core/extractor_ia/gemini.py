"""GeminiExtractor - fallback dual-API usando el SDK vigente google-genai."""

import importlib
import logging
import time
from typing import Any, Optional

from core.extractor_ia.base import ExtractorIA

logger = logging.getLogger("scraping")

_ERRORES_RETRYABLES = (
    "429", "rate", "quota", "503", "502", "500",
    "unavailable", "deadline", "timeout", "connection",
)


class GeminiExtractor(ExtractorIA):
    """Extractor con fallback automatico entre dos API keys de Gemini."""

    def __init__(
        self,
        api_key_primaria: str,
        modelo_primario: str,
        api_key_secundaria: Optional[str] = None,
        modelo_secundario: Optional[str] = None,
        temperatura: float = 0.0,
        response_mime_type: str = "application/json",
    ):
        self._apis: list[tuple[str, str, str]] = []
        if api_key_primaria:
            self._apis.append((api_key_primaria, modelo_primario, "API-1"))
        if api_key_secundaria and modelo_secundario:
            self._apis.append((api_key_secundaria, modelo_secundario, "API-2"))

        self._temperatura = temperatura
        self._mime = response_mime_type
        self._clients: list[tuple[Any, str, str]] = []
        self._disponible = False

        if not self._apis:
            logger.warning("Ninguna API key de Gemini suministrada.")
            return

        try:
            genai = importlib.import_module("google.genai")
        except ImportError:
            logger.warning("google-genai no instalado. IA deshabilitada.")
            return

        for api_key, modelo, label in self._apis:
            self._clients.append((genai.Client(api_key=api_key), modelo, label))
            logger.info(f"Gemini {label} configurada: {modelo}")
        self._disponible = True

    def disponible(self) -> bool:
        return self._disponible

    def generar(self, prompt: str, max_reintentos: int = 2) -> Optional[str]:
        """Intenta la primaria con reintentos; si agota, usa la secundaria."""
        if not self._disponible:
            return None

        for i_api, (client, modelo, label) in enumerate(self._clients):
            for intento in range(max_reintentos + 1):
                try:
                    response = client.models.generate_content(
                        model=modelo,
                        contents=prompt,
                        config={
                            "temperature": self._temperatura,
                            "response_mime_type": self._mime,
                        },
                    )
                    if i_api > 0:
                        logger.info(f"Gemini: respuesta exitosa con {label}")
                    return response.text
                except Exception as e:
                    es_str = str(e).lower()
                    es_retryable = any(err in es_str for err in _ERRORES_RETRYABLES)
                    quedan_apis = i_api + 1 < len(self._clients)

                    if es_retryable and intento < max_reintentos:
                        espera = 15 * (intento + 1)
                        logger.warning(
                            f"[{label}] Rate-limit/caida. "
                            f"Reintento {intento + 1}/{max_reintentos} en {espera}s..."
                        )
                        time.sleep(espera)
                    else:
                        accion = (
                            "Cambiando a API alternativa..." if quedan_apis
                            else "No hay mas APIs disponibles."
                        )
                        if es_retryable:
                            logger.warning(f"[{label}] Reintentos agotados. {accion}")
                        else:
                            logger.error(f"[{label}] Error no retryable: {e}. {accion}")
                        break

        logger.error("Todas las APIs de Gemini fallaron para esta solicitud.")
        return None
