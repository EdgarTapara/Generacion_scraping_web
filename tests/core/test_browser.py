"""
Tests de core/browser/. Sin llamadas a red: se mockea undetected-chromedriver.
"""

from unittest.mock import MagicMock, patch

import pytest

from core.browser import BrowserManager, buscar_texto, buscar_texto_rapido


@patch("core.browser.manager.uc.Chrome")
def test_browser_manager_lazy_init(mock_chrome):
    """El driver no se crea hasta la primera llamada."""
    mock_chrome.return_value = MagicMock()
    bm = BrowserManager(headless=True)
    assert bm._driver is None
    bm.get_driver()
    assert mock_chrome.call_count == 1
    # Segunda llamada no crea otro driver
    bm.get_driver()
    assert mock_chrome.call_count == 1


@patch("core.browser.manager.sleep")
@patch("core.browser.manager.uc.Chrome")
def test_browser_manager_navegar_listado_usa_delay_listado(mock_chrome, mock_sleep):
    mock_chrome.return_value = MagicMock()
    bm = BrowserManager(delay_listado=(1.0, 1.0), delay_detalle=(5.0, 5.0))
    bm.navegar("https://ejemplo.com", tipo="listado")
    # El sleep debe haberse llamado con un valor del rango listado (1.0)
    args, _ = mock_sleep.call_args
    assert args[0] == 1.0


@patch("core.browser.manager.sleep")
@patch("core.browser.manager.uc.Chrome")
def test_browser_manager_context_manager_cierra(mock_chrome, mock_sleep):
    driver = MagicMock()
    mock_chrome.return_value = driver
    with BrowserManager() as bm:
        bm.get_driver()
    # Al salir del context, quit fue invocado
    driver.quit.assert_called_once()


def test_buscar_texto_rapido_retorna_none_si_no_existe():
    parent = MagicMock()
    parent.find_element.side_effect = Exception("no encontrado")
    assert buscar_texto_rapido(parent, "css", ".inexistente") is None


def test_buscar_texto_rapido_retorna_texto_stripped():
    parent = MagicMock()
    elem = MagicMock()
    elem.text = "  Hola  "
    parent.find_element.return_value = elem
    assert buscar_texto_rapido(parent, "css", ".ok") == "Hola"


def test_buscar_texto_rapido_retorna_none_en_texto_vacio():
    parent = MagicMock()
    elem = MagicMock()
    elem.text = "   "
    parent.find_element.return_value = elem
    assert buscar_texto_rapido(parent, "css", ".vacio") is None
