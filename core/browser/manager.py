"""
BrowserManager — una única instancia de Chrome reutilizada por toda la corrida.

Extraído de v1/utils.py (líneas 28-92). La generalización respecto a v1 es
parametrizar los delays por tipo de página (listado vs detalle) desde el
caller, para no acoplar core a config.py de un sector específico.
"""

import logging
import random
from time import sleep

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

logger = logging.getLogger("scraping")


class BrowserManager:
    """Gestiona una única instancia de Chrome reutilizada para todo el proceso.

    Parametros:
        headless: correr Chrome en modo sin UI (primera carga de sitios con
            Cloudflare puede requerir modo no-headless).
        delay_listado: (min, max) segundos a esperar tras navegar a una
            página de listado. Se sortea uniforme.
        delay_detalle: (min, max) segundos a esperar tras navegar a una
            página de detalle.
        timeout_elemento: segundos máximos de WebDriverWait al buscar un
            elemento con selectores.
    """

    def __init__(
        self,
        headless: bool = False,
        delay_listado: tuple[float, float] = (2.0, 4.0),
        delay_detalle: tuple[float, float] = (2.0, 5.0),
        timeout_elemento: int = 8,
    ):
        self._driver = None
        self._headless = headless
        self._delay_listado = delay_listado
        self._delay_detalle = delay_detalle
        self.timeout_elemento = timeout_elemento

    def get_driver(self):
        if self._driver is None:
            opts = uc.ChromeOptions()
            opts.add_argument("--no-sandbox")
            opts.add_argument("--disable-dev-shm-usage")
            opts.add_argument("--disable-gpu")
            opts.add_argument("--window-size=1920,1080")
            if self._headless:
                opts.add_argument("--headless=new")
            self._driver = uc.Chrome(options=opts, version_main=None)
            logger.info("Chrome (undetected) iniciado correctamente")
        return self._driver

    def navegar(self, url: str, tipo: str = "detalle"):
        """Navega a la URL, espera aleatoriamente y cierra banners de cookies."""
        driver = self.get_driver()
        driver.get(url)
        delay_min, delay_max = (
            self._delay_listado if tipo == "listado" else self._delay_detalle
        )
        sleep(random.uniform(delay_min, delay_max))
        self._cerrar_cookies(driver)
        return driver

    def _cerrar_cookies(self, driver):
        """Intenta cerrar banners de cookies comunes (best-effort, nunca falla)."""
        try:
            btn = WebDriverWait(driver, 0.5).until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//button[contains(text(), 'acepto')]")
                )
            )
            btn.click()
        except Exception:
            pass
        try:
            banner = driver.find_element(
                By.CSS_SELECTOR, '[data-qa="cookies-policy-banner"]'
            )
            banner.click()
        except Exception:
            pass

    def cerrar(self):
        """Cierra el navegador."""
        if self._driver:
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
