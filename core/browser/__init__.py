"""Gestión del navegador Selenium/undetected-chromedriver."""

from core.browser.manager import BrowserManager
from core.browser.selectors import buscar_texto, buscar_texto_rapido

__all__ = ["BrowserManager", "buscar_texto", "buscar_texto_rapido"]
