"""HTTP-first: cliente `requests` reusable + detección de anti-bot.

Política del framework (lección del sector empleo): **no abrir un navegador
por defecto**. La mayoría de portales sirven HTML server-side, JSON o XHR
y se resuelven con `requests`, que es más rápido, estable y barato que
Selenium. El navegador (`core.browser`) se reserva para el momento exacto
en que un portal exige fingerprint real, que `detectar_bloqueo_anti_bot`
identifica para escalar de forma informada.
"""

from core.http.anti_bot import detectar_bloqueo_anti_bot
from core.http.cliente import HttpClient

__all__ = ["HttpClient", "detectar_bloqueo_anti_bot"]
