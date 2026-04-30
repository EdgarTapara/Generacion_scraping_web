"""
Interfaz abstracta para extractores IA.

Cada sector implementa prompts específicos (ubicación urbana para inmobiliario,
CIIU para empleo, etc.). El contrato común es: dada una lista de registros y
un prompt template, devolver una lista de dicts con los campos enriquecidos.
"""

from abc import ABC, abstractmethod
from typing import Any


class ExtractorIA(ABC):
    """Contrato base que cualquier extractor IA debe cumplir.

    La implementación concreta decide cómo llamar al proveedor (Gemini,
    Ollama, OpenAI, etc.) y cómo parsear la respuesta. El caller pasa el
    prompt ya formateado con el payload del batch embebido.
    """

    @abstractmethod
    def disponible(self) -> bool:
        """¿El extractor tiene credenciales y librería disponibles?"""

    @abstractmethod
    def generar(self, prompt: str, max_reintentos: int = 2) -> str | None:
        """Llama al modelo y devuelve el texto (usualmente JSON). None si falla."""

    def enriquecer_batch(
        self,
        registros: list[dict[str, Any]],
        prompt_template: str,
        tamano_lote: int = 20,
        pausa_entre_lotes: float = 2.0,
    ) -> list[dict[str, Any]]:
        """Procesa los registros en lotes y devuelve las respuestas parseadas.

        El `prompt_template` debe contener el placeholder `{payload}` que se
        reemplaza con la lista JSON del lote. Cada elemento del lote se asume
        como dict con al menos la clave `id` (para remapear la respuesta).

        Respuesta por cada lote: se espera JSON con lista de dicts. Los
        elementos que no se puedan parsear se omiten silenciosamente — el
        caller decide si lanzar fallback determinista.
        """
        import json
        import time

        resultados: list[dict[str, Any]] = []
        if not self.disponible() or not registros:
            return resultados

        for inicio in range(0, len(registros), tamano_lote):
            lote = registros[inicio:inicio + tamano_lote]
            payload = json.dumps(lote, ensure_ascii=False)
            prompt = prompt_template.replace("{payload}", payload)

            respuesta = self.generar(prompt)
            if not respuesta:
                continue

            try:
                datos = json.loads(respuesta)
                if isinstance(datos, list):
                    resultados.extend(d for d in datos if isinstance(d, dict))
            except json.JSONDecodeError:
                continue

            if inicio + tamano_lote < len(registros):
                time.sleep(pausa_entre_lotes)

        return resultados
