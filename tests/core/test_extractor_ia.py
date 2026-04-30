"""Tests del contrato `ExtractorIA` y del extractor Gemini (sin red)."""

import sys
import types
from unittest.mock import patch

from core.extractor_ia import ExtractorIA, GeminiExtractor


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


def test_gemini_extractor_sin_keys_no_disponible():
    ext = GeminiExtractor(
        api_key_primaria="", modelo_primario="",
        api_key_secundaria=None, modelo_secundario=None,
    )
    assert ext.disponible() is False
    assert ext.generar("hola") is None


def test_gemini_extractor_usa_google_genai(monkeypatch):
    """El extractor debe usar el SDK vigente `google.genai`, no el deprecado."""
    created_clients = []

    class FakeModels:
        def generate_content(self, *, model, contents, config):
            assert model == "m1"
            assert contents == "prompt"
            assert config["temperature"] == 0.0
            assert config["response_mime_type"] == "application/json"

            class R:
                text = '[{"id": 0}]'
            return R()

    class FakeClient:
        def __init__(self, api_key):
            created_clients.append(api_key)
            self.models = FakeModels()

    fake_google = types.ModuleType("google")
    fake_genai = types.SimpleNamespace(Client=FakeClient)
    monkeypatch.setitem(sys.modules, "google", fake_google)
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai)

    ext = GeminiExtractor(
        api_key_primaria="k1", modelo_primario="m1",
        api_key_secundaria=None, modelo_secundario=None,
    )

    assert ext.disponible() is True
    assert ext.generar("prompt") == '[{"id": 0}]'
    assert created_clients == ["k1"]


def test_gemini_extractor_fallback_a_segunda_api(monkeypatch):
    """Primera API tira error retryable; segunda responde OK."""
    calls = {"n": 0}

    class FakeModels:
        def __init__(self, api_key):
            self.api_key = api_key

        def generate_content(self, *, model, contents, config):
            calls["n"] += 1
            if self.api_key == "k1":
                raise Exception("429 rate limit exceeded")

            class R:
                text = '[{"id": 0}]'
            return R()

    class FakeClient:
        def __init__(self, api_key):
            self.models = FakeModels(api_key)

    fake_google = types.ModuleType("google")
    fake_genai = types.SimpleNamespace(Client=FakeClient)
    monkeypatch.setitem(sys.modules, "google", fake_google)
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai)

    # Parchar time.sleep para no esperar los reintentos.
    with patch("core.extractor_ia.gemini.time.sleep"):
        ext = GeminiExtractor(
            api_key_primaria="k1", modelo_primario="m1",
            api_key_secundaria="k2", modelo_secundario="m2",
        )
        resultado = ext.generar("prompt")
        assert resultado == '[{"id": 0}]'
        assert calls["n"] == 4
