"""
Helpers de selección DOM sobre un driver Selenium ya navegado.

Extraído de v1/utils.py (líneas 99-126).
"""

from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


def buscar_texto(driver, selectores: list, timeout: int = 8) -> str | None:
    """Intenta múltiples selectores (by_type, valor) en orden.

    Retorna el texto del primero que funcione, o None si ninguno matcheó.
    """
    for by_type, selector in selectores:
        try:
            elem = WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((by_type, selector))
            )
            texto = elem.text.strip()
            if texto:
                return texto
        except Exception:
            continue
    return None


def buscar_texto_rapido(parent, by_type, selector: str) -> str | None:
    """Búsqueda sin espera explícita, para elementos ya cargados en la tarjeta."""
    try:
        elem = parent.find_element(by_type, selector)
        texto = elem.text.strip()
        return texto if texto else None
    except Exception:
        return None
