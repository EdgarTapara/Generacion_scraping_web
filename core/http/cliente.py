"""Cliente HTTP genérico con retries, throttle y headers humanos.

Reutilizable por portales que prefieren ``requests`` sobre un navegador.
La lección de empleo (3 de 4 portales sin Selenium) es que **abrir Chrome
por defecto es caro y casi nunca necesario**: si el portal sirve HTML
server-side, JSON o un XHR/JSON-LD, `requests` basta y es órdenes de
magnitud más rápido y estable. El navegador (`core.browser`) se reserva
para cuando el portal exige fingerprint real (ver `core.http.anti_bot`).

Detalle no obvio: el `connect_timeout_s` corto evita que un host
bloqueado por firewall cuelgue la corrida ``read_timeout × retries``.
``requests`` acepta la tupla ``(connect, read)``; un host caído cae en
segundos en vez de minutos (caso real SERVIR: ~12 s en vez de ~90 s).
"""

from __future__ import annotations

import logging
import time
from typing import Any
from urllib.parse import urljoin

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger("scraping")

_DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


class HttpClient:
    """Wrap fino sobre `requests.Session` con retries y throttle inter-llamada."""

    def __init__(
        self,
        base_url: str,
        *,
        throttle_s: float = 1.0,
        timeout_s: float = 30.0,
        connect_timeout_s: float | None = None,
        retries: int = 3,
        user_agent: str | None = None,
        accept_json: bool = True,
    ) -> None:
        self.base_url = base_url.rstrip("/") + "/"
        self.throttle_s = max(0.0, float(throttle_s))
        self.timeout_s = float(timeout_s)
        self._timeout = (
            (float(connect_timeout_s), self.timeout_s)
            if connect_timeout_s is not None
            else self.timeout_s
        )
        self._ultima_llamada_mono: float = 0.0

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": user_agent or _DEFAULT_UA,
            "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
        })
        if accept_json:
            self.session.headers["Accept"] = "application/json, text/plain, */*"

        retry = Retry(
            total=retries,
            backoff_factor=1.0,
            status_forcelist=(429, 500, 502, 503, 504),
            # POST incluido para postbacks idempotentes (JSF: filtro, paginación).
            allowed_methods=frozenset(["GET", "HEAD", "POST"]),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def _esperar_throttle(self) -> None:
        if self.throttle_s <= 0:
            return
        ahora = time.monotonic()
        delta = ahora - self._ultima_llamada_mono
        if delta < self.throttle_s:
            time.sleep(self.throttle_s - delta)
        self._ultima_llamada_mono = time.monotonic()

    def _resolver(self, path: str) -> str:
        if path.startswith("http://") or path.startswith("https://"):
            return path
        return urljoin(self.base_url, path.lstrip("/"))

    def get(
        self,
        path: str,
        *,
        params: dict | None = None,
        headers: dict | None = None,
    ) -> requests.Response:
        url = self._resolver(path)
        self._esperar_throttle()
        logger.debug("HTTP GET %s params=%s", url, params)
        r = self.session.get(url, params=params, headers=headers, timeout=self._timeout)
        if r.status_code >= 400:
            logger.warning("HTTP %s %s -> %s", r.request.method, r.url, r.status_code)
            r.raise_for_status()
        return r

    def post(
        self,
        path: str,
        *,
        data: dict | None = None,
        headers: dict | None = None,
    ) -> requests.Response:
        url = self._resolver(path)
        self._esperar_throttle()
        logger.debug("HTTP POST %s data_keys=%s", url, sorted((data or {}).keys()))
        r = self.session.post(url, data=data, headers=headers, timeout=self._timeout)
        if r.status_code >= 400:
            logger.warning("HTTP %s %s -> %s", r.request.method, r.url, r.status_code)
            r.raise_for_status()
        return r

    def get_json(self, path: str, *, params: dict | None = None) -> Any:
        r = self.get(path, params=params, headers={"Accept": "application/json"})
        return r.json()

    def close(self) -> None:
        self.session.close()
