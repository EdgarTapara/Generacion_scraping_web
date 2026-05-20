"""
BrowserManager — una única instancia de Chrome reutilizada por toda la corrida.

Patrones que merece la pena conocer (todos validados en producción en v1):

* **Una sola instancia de Chrome para todo el scraping.** Abrir un Chrome
  por anuncio levanta sospechas de bot e infla el footprint de memoria.
  Reutilizar el driver además garantiza que los delays anti-bot se
  cumplen entre páginas, no se "reinician" a cero al cerrar y abrir.

* **`undetected_chromedriver` vs `selenium` puro.** El primero parchea la
  huella de Chromium (var `navigator.webdriver`, fingerprint del CDP, etc.)
  para esquivar la detección de Cloudflare/DataDome que tienen los portales
  inmobiliarios y de empleo peruanos. Cambiar a Selenium puro suele romper
  las primeras corridas tras una actualización de Chrome.

* **Monkeypatch de `Chrome.__del__`.** En Windows, el destructor del driver
  intenta cerrar un proceso que ya pudo morir y lanza `OSError WinError 6`.
  Lo envolvemos en try/except para que la corrida termine limpio.

* **Override opcional `CHROME_VERSION_MAIN`.** Si la autodetección falla
  (suele pasar tras un Chrome update), el caller puede fijar la versión
  via env var sin recompilar nada.

* **Delays parametrizados por tipo de página.** Listado vs detalle tienen
  perfiles distintos: en listado se aceptan delays más cortos porque
  hay menos ruido detectable; en detalle es donde el portal mide más.
"""

from __future__ import annotations

import logging
import os
import random
from time import sleep
from typing import Iterable

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

logger = logging.getLogger("scraping")

# ---------------------------------------------------------------------------
# Monkeypatch para evitar OSError (WinError 6) al destruir el objeto Chrome.
# v1 ya tenía este parche; se aplica al importar el módulo, idempotente.
# ---------------------------------------------------------------------------
_original_del = uc.Chrome.__del__


def _safe_del(self) -> None:
    try:
        _original_del(self)
    except Exception:
        pass


uc.Chrome.__del__ = _safe_del


# Selectores comunes de cookies banners en portales peruanos y latam.
# Si un sector tiene uno propio, lo agrega por constructor.
_SELECTORES_COOKIES_DEFAULT: tuple[tuple[str, str], ...] = (
    ("xpath", "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'acepto')]"),
    ("xpath", "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'aceptar')]"),
    ("css", '[data-qa="cookies-policy-banner"]'),
    ("css", "#onetrust-accept-btn-handler"),
    ("css", "button.cookies-accept"),
)


def _to_by(kind: str):
    return By.XPATH if kind.lower() == "xpath" else By.CSS_SELECTOR


class BrowserManager:
    """Gestiona una única instancia de Chrome reutilizada para todo el proceso.

    Parámetros:
        headless: correr Chrome sin UI. Cloudflare puede pedir captcha
            cuando se detecta headless en sitios "duros"; por defecto False.
        delay_listado / delay_detalle: tuplas (min, max) en segundos para el
            sleep aleatorio tras navegar. El sorteo uniforme evita patrones
            detectables (delays exactos == bot).
        timeout_elemento: límite para WebDriverWait en `core.browser.selectors`.
        version_main: override de la versión de Chrome para
            `undetected_chromedriver`. None = autodetección.
            Si la env var `CHROME_VERSION_MAIN` está seteada se usa como
            fallback cuando no se pasó explícitamente.
        selectores_cookies: iterable de (kind, selector) adicional a los
            defaults para cerrar banners específicos del portal.
        extra_args: argumentos adicionales para Chrome (ej. proxy).
    """

    def __init__(
        self,
        headless: bool = False,
        delay_listado: tuple[float, float] = (2.0, 4.0),
        delay_detalle: tuple[float, float] = (2.0, 5.0),
        timeout_elemento: int = 8,
        version_main: int | None = None,
        selectores_cookies: Iterable[tuple[str, str]] | None = None,
        extra_args: Iterable[str] = (),
    ):
        self._driver = None
        self._headless = headless
        self._delay_listado = delay_listado
        self._delay_detalle = delay_detalle
        self.timeout_elemento = timeout_elemento

        env_version = os.getenv("CHROME_VERSION_MAIN", "").strip()
        if version_main is None and env_version:
            try:
                version_main = int(env_version)
            except ValueError:
                logger.warning(
                    "CHROME_VERSION_MAIN=%r no es entero válido. Se autodetecta.",
                    env_version,
                )
        self._version_main = version_main

        self._selectores_cookies: tuple[tuple[str, str], ...] = tuple(
            list(_SELECTORES_COOKIES_DEFAULT) + list(selectores_cookies or [])
        )
        self._extra_args: tuple[str, ...] = tuple(extra_args)

    # -----------------------------------------------------------------
    # Inicialización del driver
    # -----------------------------------------------------------------

    def _construir_opciones(self) -> uc.ChromeOptions:
        opts = uc.ChromeOptions()
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--window-size=1920,1080")
        if self._headless:
            opts.add_argument("--headless=new")
        for arg in self._extra_args:
            opts.add_argument(arg)
        return opts

    def _iniciar_driver(self, opts: uc.ChromeOptions):
        """Intenta version_main si está fijada; cae a autodetección si falla."""
        if self._version_main is not None:
            logger.info(
                "Iniciando Chrome (undetected) con version_main=%s",
                self._version_main,
            )
            try:
                return uc.Chrome(options=opts, version_main=self._version_main)
            except Exception as exc:
                logger.warning(
                    "Fallo al iniciar Chrome con version_main=%s: %s. "
                    "Reintentando con autodetección.",
                    self._version_main,
                    exc,
                )
        return uc.Chrome(options=opts)

    def get_driver(self):
        if self._driver is None:
            self._driver = self._iniciar_driver(self._construir_opciones())
            logger.info("Chrome (undetected) iniciado correctamente")
        return self._driver

    # -----------------------------------------------------------------
    # Navegación
    # -----------------------------------------------------------------

    def navegar(self, url: str, tipo: str = "detalle"):
        """Navega, aplica delay aleatorio y cierra banners de cookies."""
        driver = self.get_driver()
        driver.get(url)
        delay_min, delay_max = (
            self._delay_listado if tipo == "listado" else self._delay_detalle
        )
        sleep(random.uniform(delay_min, delay_max))
        self._cerrar_cookies(driver)
        return driver

    def _cerrar_cookies(self, driver) -> None:
        """Best-effort: prueba todos los selectores conocidos, nunca lanza."""
        for kind, selector in self._selectores_cookies:
            try:
                elem = WebDriverWait(driver, 0.5).until(
                    EC.element_to_be_clickable((_to_by(kind), selector))
                )
                elem.click()
                return
            except Exception:
                continue

    # -----------------------------------------------------------------
    # Cierre
    # -----------------------------------------------------------------

    def cerrar(self) -> None:
        """Cierra el navegador de forma segura (Windows-safe)."""
        if self._driver is None:
            return
        try:
            self._driver.quit()
        except Exception:
            pass
        # Nulificar service para que __del__ del GC no intente quit() otra vez
        # (bug conocido de undetected_chromedriver en Windows).
        try:
            self._driver.service = None
        except Exception:
            pass
        self._driver = None
        logger.info("Chrome cerrado")

    def __enter__(self):
        self.get_driver()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cerrar()
        return False
