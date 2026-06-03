"""Tests de core.http (HTTP-first) sin red."""

from core.http import HttpClient, detectar_bloqueo_anti_bot


class _FakeResp:
    status_code = 200
    url = "https://x.com/"


def test_resolver_relativo_y_absoluto():
    c = HttpClient("https://x.com/api", throttle_s=0)
    assert c._resolver("foo") == "https://x.com/api/foo"
    assert c._resolver("/foo") == "https://x.com/api/foo"
    assert c._resolver("https://y.com/z") == "https://y.com/z"


def test_connect_timeout_se_pasa_como_tupla(monkeypatch):
    c = HttpClient("https://x.com", throttle_s=0, timeout_s=30, connect_timeout_s=5)
    capturado = {}

    def fake_get(url, params=None, headers=None, timeout=None):
        capturado["timeout"] = timeout
        return _FakeResp()

    monkeypatch.setattr(c.session, "get", fake_get)
    c.get("/")
    # Tupla (connect, read): un host bloqueado cae en ~5s, no en 30s × retries.
    assert capturado["timeout"] == (5.0, 30.0)


def test_sin_connect_timeout_usa_escalar(monkeypatch):
    c = HttpClient("https://x.com", throttle_s=0, timeout_s=20)
    capturado = {}
    monkeypatch.setattr(
        c.session, "get",
        lambda url, params=None, headers=None, timeout=None: (
            capturado.update(timeout=timeout) or _FakeResp()
        ),
    )
    c.get("/")
    assert capturado["timeout"] == 20.0


def test_anti_bot_status():
    assert detectar_bloqueo_anti_bot(403, "lo que sea")
    assert detectar_bloqueo_anti_bot(429, None)


def test_anti_bot_challenge_en_texto():
    assert detectar_bloqueo_anti_bot(200, "Just a moment... checking your browser")
    assert detectar_bloqueo_anti_bot(503, "cf-chl bypass / cdn-cgi/challenge")


def test_anti_bot_respuesta_normal_es_none():
    assert detectar_bloqueo_anti_bot(200, "<html><body>casa en venta</body></html>") is None
    assert detectar_bloqueo_anti_bot(200, None) is None
