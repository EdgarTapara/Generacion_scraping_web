"""
Conversión de fechas relativas / absolutas en español a ISO 8601.

Generaliza v1/limpieza.py:limpiar_fecha. La lógica aplica a cualquier portal
en español peruano (inmobiliario, empleo, etc.) que use frases como
"publicado hace 3 días" o "23 may. 2026".
"""

import re
from datetime import datetime, timedelta
from typing import Optional


_MESES_ES = {
    "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
    "jul": 7, "ago": 8, "set": 9, "sep": 9, "oct": 10, "nov": 11, "dic": 12,
}


def limpiar_fecha_relativa(
    fecha_raw: str | None,
    referencia: Optional[datetime] = None,
) -> str | None:
    """Convierte fecha relativa o absoluta en español a formato ISO YYYY-MM-DD.

    Ejemplos:
        "Publicado desde ayer"            → referencia - 1 día
        "Publicado hace 3 dias"           → referencia - 3 días
        "Publicado hace 1 semana, 5 dias" → referencia - 12 días
        "Publicado hace 1 hora"           → referencia (< 24 h = hoy)
        "Publicado hoy"                   → referencia
        "Publicado 23 may. 2026"          → "2026-05-23"

    Si `referencia` es None se usa `datetime.now()` (facilita testing pasar
    una fecha fija).
    """
    if not isinstance(fecha_raw, str) or not fecha_raw.strip():
        return None

    texto = fecha_raw.lower().strip()
    hoy = referencia or datetime.now()

    # Fecha absoluta: "23 may. 2026", "6 ene. 2026", "27 mar 2026"
    match = re.search(r"(\d{1,2})\s+([a-z]{3,4})\.?\s+(\d{4})", texto)
    if match:
        dia = int(match.group(1))
        mes_txt = match.group(2)[:3]
        anio = int(match.group(3))
        mes = _MESES_ES.get(mes_txt)
        if mes:
            try:
                return datetime(anio, mes, dia).strftime("%Y-%m-%d")
            except ValueError:
                pass

    if "hoy" in texto:
        return hoy.strftime("%Y-%m-%d")

    if "ayer" in texto:
        return (hoy - timedelta(days=1)).strftime("%Y-%m-%d")

    # "hace N hora[s]" → mismo día
    if re.search(r"hace\s+\d+\s*hora", texto):
        return hoy.strftime("%Y-%m-%d")

    # Combinar semanas + días + meses (granularidad de días)
    total_dias = 0
    encontrado = False

    match = re.search(r"hace\s+(\d+)\s*semanas?", texto)
    if match:
        total_dias += int(match.group(1)) * 7
        encontrado = True

    match = re.search(r"(\d+)\s*d[ií]as?", texto)
    if match and "hace" in texto:
        total_dias += int(match.group(1))
        encontrado = True

    match = re.search(r"hace\s+(\d+)\s*mes(?:es)?", texto)
    if match:
        total_dias += int(match.group(1)) * 30
        encontrado = True

    if encontrado:
        return (hoy - timedelta(days=total_dias)).strftime("%Y-%m-%d")

    return None
