"""
Parseo de números desde texto libre. Extraído de v1/utils.py (líneas 129-152).
"""

import re


def parsear_numero(texto: str | None) -> float | None:
    """Extrae el primer número (int o float) de un texto. Retorna float o None."""
    if not texto:
        return None
    match = re.search(r"[\d,.]+", str(texto).replace(",", ""))
    if match:
        try:
            return float(match.group().replace(",", ""))
        except ValueError:
            return None
    return None


def parsear_entero(texto: str | None) -> int | None:
    """Extrae el primer entero de un texto. Retorna int o None."""
    if not texto:
        return None
    match = re.search(r"\d+", str(texto))
    if match:
        try:
            return int(match.group())
        except ValueError:
            return None
    return None
