"""Tests del contrato `ExtractorIA` y del extractor DeepSeek (sin red)."""

import sys
import types
from unittest.mock import patch

from core.extractor_ia import DeepSeekExtractor, ExtractorIA


class ExtractorFalso(ExtractorIA):
    """Implementacion dummy que devuelve una respuesta precanned."""

    def __init__(self, respuesta: str | None):
        self._r = respuesta
        self.llamadas = 0

    def disponible(self) -> bool:
        return self._r is not None

    def generar(self, prompt, max_reintentos=2):
        self.llamadas += 1
        return self._r


def test_enriquecer_batch_parsea_json():
    ext = ExtractorFalso('[{"id": 0, "ubicacion": "Av. Ejercito 120"}]')
    resultado = ext.enriquecer_batch(
        registros=[{"id": 0, "descripcion": "algo"}],
        prompt_template="procesa: {payload}",
        tamano_lote=20,
        pausa_entre_lotes=0,
    )
    assert resultado == [{"id": 0, "ubicacion": "Av. Ejercito 120"}]
    assert ext.llamadas == 1


def test_enriquecer_batch_ignora_json_invalido():
    ext = ExtractorFalso("no soy json")
    resultado = ext.enriquecer_batch(
        registros=[{"id": 0}],
        prompt_template="{payload}",
        pausa_entre_lotes=0,
    )
    assert resultado == []


def test_enriquecer_batch_omite_si_no_disponible():
    ext = ExtractorFalso(None)
    resultado = ext.enriquecer_batch(
        registros=[{"id": 0}],
        prompt_template="{payload}",
        pausa_entre_lotes=0,
    )
    assert resultado == []
    assert ext.llamadas == 0


def test_deepseek_extractor_sin_key_no_disponible():
    ext = DeepSeekExtractor(api_key="", modelo_primario="", modelo_secundario=None)
    assert ext.disponible() is False
    assert ext.generar("hola") is None


def test_deepseek_extractor_usa_openai_compatible(monkeypatch):
    created_clients = []

    class FakeCompletions:
        def create(self, *, model, messages, response_format, temperature):
            assert model == "deepseek-v4-flash"
            assert messages[-1]["content"] == "prompt"
            assert response_format == {"type": "json_object"}
            assert temperature == 0.0

            class Msg:
                content = '{"items": [{"id": 0}]}'

            class Choice:
                message = Msg()

            class Response:
                choices = [Choice()]

            return Response()

    class FakeOpenAI:
        def __init__(self, *, api_key, base_url, timeout):
            created_clients.append((api_key, base_url, timeout))
            self.chat = types.SimpleNamespace(
                completions=FakeCompletions()
            )

    fake_openai = types.SimpleNamespace(OpenAI=FakeOpenAI)
    monkeypatch.setitem(sys.modules, "openai", fake_openai)

    ext = DeepSeekExtractor(api_key="k1", modelo_primario="deepseek-v4-flash")

    assert ext.disponible() is True
    assert ext.generar("prompt") == '{"items": [{"id": 0}]}'
    assert created_clients == [("k1", "https://api.deepseek.com", 60.0)]


def test_deepseek_extractor_fallback_a_modelo_secundario(monkeypatch):
    calls = []

    class FakeCompletions:
        def create(self, *, model, messages, response_format, temperature):
            calls.append(model)
            if model == "deepseek-v4-flash":
                raise Exception("429 rate limit exceeded")

            class Msg:
                content = '{"items": [{"id": 0}]}'

            class Choice:
                message = Msg()

            class Response:
                choices = [Choice()]

            return Response()

    class FakeOpenAI:
        def __init__(self, *, api_key, base_url, timeout):
            self.chat = types.SimpleNamespace(
                completions=FakeCompletions()
            )

    fake_openai = types.SimpleNamespace(OpenAI=FakeOpenAI)
    monkeypatch.setitem(sys.modules, "openai", fake_openai)

    with patch("core.extractor_ia.deepseek.time.sleep"):
        ext = DeepSeekExtractor(
            api_key="k1",
            modelo_primario="deepseek-v4-flash",
            modelo_secundario="deepseek-v4-pro",
        )
        resultado = ext.generar("prompt")

    assert resultado == '{"items": [{"id": 0}]}'
    assert calls == [
        "deepseek-v4-flash",
        "deepseek-v4-flash",
        "deepseek-v4-flash",
        "deepseek-v4-pro",
    ]
