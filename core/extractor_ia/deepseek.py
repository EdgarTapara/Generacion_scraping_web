"""DeepSeekExtractor - cliente OpenAI-compatible con fallback de modelos."""

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


class DeepSeekExtractor(ExtractorIA):
    """Extractor IA de bajo costo usando DeepSeek via SDK OpenAI-compatible."""

    def __init__(
        self,
        api_key: str,
        modelo_primario: str,
        modelo_secundario: Optional[str] = None,
        base_url: str = "https://api.deepseek.com",
        timeout: float = 60.0,
        temperatura: float = 0.0,
        response_format: Optional[dict[str, str]] = None,
        system_prompt: Optional[str] = None,
    ):
        self._modelos: list[tuple[str, str]] = []
        if api_key and modelo_primario:
            self._modelos.append((modelo_primario, "Flash"))
        if api_key and modelo_secundario:
            self._modelos.append((modelo_secundario, "Pro"))

        self._temperatura = temperatura
        self._response_format = response_format or {"type": "json_object"}
        self._system_prompt = system_prompt
        self._client: Any = None
        self._disponible = False

        if not api_key or not self._modelos:
            logger.warning("DEEPSEEK_API_KEY no configurada. IA deshabilitada.")
            return

        try:
            openai = importlib.import_module("openai")
        except ImportError:
            logger.warning("openai no instalado. IA deshabilitada.")
            return

        self._client = openai.OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)
        self._disponible = True
        logger.info(
            "DeepSeek configurado: %s",
            " | ".join(f"{label}: {modelo}" for modelo, label in self._modelos),
        )

    def disponible(self) -> bool:
        return self._disponible

    def generar(self, prompt: str, max_reintentos: int = 2) -> Optional[str]:
        """Intenta el modelo primario y cambia al secundario si falla."""
        if not self._disponible:
            return None

        messages = []
        if self._system_prompt:
            messages.append({"role": "system", "content": self._system_prompt})
        messages.append({"role": "user", "content": prompt})

        for i_modelo, (modelo, label) in enumerate(self._modelos):
            for intento in range(max_reintentos + 1):
                try:
                    response = self._client.chat.completions.create(
                        model=modelo,
                        messages=messages,
                        response_format=self._response_format,
                        temperature=self._temperatura,
                    )
                    if i_modelo > 0:
                        logger.info(f"DeepSeek: respuesta exitosa con {label}")
                    return response.choices[0].message.content
                except Exception as e:
                    es_str = str(e).lower()
                    es_retryable = any(err in es_str for err in _ERRORES_RETRYABLES)
                    quedan_modelos = i_modelo + 1 < len(self._modelos)

                    if es_retryable and intento < max_reintentos:
                        espera = 15 * (intento + 1)
                        logger.warning(
                            f"[{label}] Rate-limit/caida. "
                            f"Reintento {intento + 1}/{max_reintentos} en {espera}s..."
                        )
                        time.sleep(espera)
                    else:
                        accion = (
                            "Cambiando a modelo alternativo..." if quedan_modelos
                            else "No hay mas modelos disponibles."
                        )
                        if es_retryable:
                            logger.warning(f"[{label}] Reintentos agotados. {accion}")
                        else:
                            logger.error(f"[{label}] Error no retryable: {e}. {accion}")
                        break

        logger.error("Todos los modelos DeepSeek fallaron para esta solicitud.")
        return None
