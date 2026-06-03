"""Detección de bloqueos anti-bot en respuestas HTTP.

Genérico y sector-agnóstico. **No intenta resolver** el bloqueo (eso es
trabajo de `core.browser` con undetected-chromedriver) — sólo lo *detecta*
para que el reporte de mantenimiento escale a la metodología correcta.

Esto es la otra cara del enfoque HTTP-first: se empieza liviano con
`requests`; si y sólo si un portal empieza a responder con un desafío
(Cloudflare / DataDome / captcha / 403 / 429) se escala al navegador.
Así se evita meter Selenium de forma preventiva "por si acaso".
"""

from __future__ import annotations

import re

# Firmas típicas de páginas de desafío (Cloudflare, DataDome, PerimeterX, captcha).
_CHALLENGE = re.compile(
    r"just a moment|checking your browser|cf-?chl|/cdn-cgi/challenge|"
    r"attention required|enable javascript and cookies|"
    r"datadome|px-captcha|perimeterx|hcaptcha|recaptcha|are you a human|"
    r"unusual traffic|verify you are human",
    re.I,
)

# Estados que, ante un GET de scraping, suelen indicar bloqueo/rate-limit.
_STATUS_BLOQUEO = {403, 429}


def detectar_bloqueo_anti_bot(status_code: int | None, texto: str | None) -> str | None:
    """Devuelve el motivo del bloqueo anti-bot, o None si la respuesta es normal.

    El caller puede guardar el motivo en `diagnostico["anti_bot"]`; el
    reporte de mantenimiento lo clasifica como `ANTI_BOT` y recomienda
    escalar a `core.browser` (ver `core.mantenimiento_frontend`).
    """
    if status_code in _STATUS_BLOQUEO:
        return f"HTTP {status_code}: posible bloqueo anti-bot / rate-limit"
    if status_code == 503 and texto and _CHALLENGE.search(texto[:20000]):
        return "HTTP 503 con página de desafío (Cloudflare/anti-bot)"
    if texto and _CHALLENGE.search(texto[:20000]):
        return "Página de desafío anti-bot detectada (Cloudflare/DataDome/captcha)"
    return None
