"""
Helpers de moneda para el contexto peruano (PEN / USD).

`moneda_a_iso` extraída de v1/utils.py (línea 249).
`limpiar_precio_pe` generalización de v1/limpieza.py:limpiar_precio
(se mantiene aquí porque cualquier sector que muestre precios en portales
peruanos se encontrará con formatos tipo "S/ 2,460 · USD 650").
"""

import re


def moneda_a_iso(currency_raw: str | None) -> str | None:
    """Convierte cualquier representación de moneda a ISO.

    'S/', 'S/.', 'PEN', 'SOLES'  → 'PEN'
    'USD', 'US$', '$', 'U$S', 'DOLARES' → 'USD'
    """
    if not currency_raw:
        return None
    c = str(currency_raw).upper().replace(" ", "").replace(".", "")
    if c in ("S/", "S/.", "PEN", "SOLES"):
        return "PEN"
    if c in ("USD", "US$", "$", "U$S", "DOLARES"):
        return "USD"
    return None


def limpiar_precio_pe(precio_raw: str | None) -> dict:
    """Parsea precios en formato peruano con posible precio primario + secundario.

    Ejemplos:
        "S/ 2,460"                   → {precio: 2460, moneda: PEN}
        "USD 650"                    → {precio: 650, moneda: USD}
        "S/ 2,460 · USD 650"         → primario PEN + secundario USD
    """
    result = {
        "precio": None,
        "moneda": None,
        "precio_secundario": None,
        "moneda_secundaria": None,
    }

    if not isinstance(precio_raw, str) or not precio_raw.strip():
        return result

    texto = precio_raw.strip()
    patron = re.compile(r"(S/|US\$|USD|U\$S|\$)\s*([\d,.\s]+)", re.IGNORECASE)
    matches = patron.findall(texto)

    for i, (moneda_raw, monto_raw) in enumerate(matches):
        moneda = moneda_a_iso(moneda_raw) or "USD"
        monto_str = monto_raw.replace(",", "").replace(" ", "").strip()
        try:
            monto = float(monto_str)
        except ValueError:
            continue
        if monto <= 0:
            continue
        if i == 0:
            result["precio"] = monto
            result["moneda"] = moneda
        elif i == 1:
            result["precio_secundario"] = monto
            result["moneda_secundaria"] = moneda

    # Último recurso: número pelado → asumir soles
    if result["precio"] is None:
        numeros = re.findall(r"[\d,]+", texto)
        if numeros:
            monto_str = numeros[0].replace(",", "")
            try:
                monto = float(monto_str)
                if monto > 0:
                    result["precio"] = monto
                    result["moneda"] = "PEN"
            except ValueError:
                pass

    return result


_PRECIO_MONEDA_RE = re.compile(
    r"(?<![A-Za-z0-9])(?P<moneda>US\s*\$|U\s*\$|\$|S\s*/\.?)\s*"
    r"(?P<numero>\d[\d.,]{0,18})",
    re.IGNORECASE,
)
_PRECIO_ALT_PEN_RE = re.compile(
    r"\b([1-9]\d{2,5}(?:[.,]\d{3})?)\s*(?:soles|mensual)\b",
    re.IGNORECASE,
)


def _normalizar_token_precio_publicado(token: str, moneda: str) -> str | None:
    """Recorta telefonos pegados al precio en avisos impresos/PDF."""
    token = re.sub(r"\s+", "", token or "")
    token = re.sub(r"[^0-9.,]", "", token)
    if not token:
        return None

    sep_match = re.search(r"[.,]", token)
    if sep_match:
        sep = sep_match.group(0)
        before, after = token.split(sep, 1)
        if not before or not after:
            return None
        if len(after) > 3:
            first3 = after[:3]
            if len(before) >= 4:
                return before
            if moneda == "PEN" and len(before) == 3 and first3.startswith("00"):
                return before
            if len(before) <= 2 and first3 == "000":
                return before + sep + first3
            return before + sep + first3
        return token

    if len(token) > 6:
        return None
    return token


def _precio_plausible(precio: float | None, moneda: str) -> bool:
    if precio is None:
        return False
    if moneda in {"PEN", "USD"}:
        return 100 <= precio <= 5_000_000
    return False


def extraer_precio_publicado_pe(texto: str | None) -> dict:
    """Extrae precio publicado solo con senal monetaria explicita.

    En clasificados PDF los telefonos pueden pegarse al monto, por ejemplo
    `$680,000959553859`. Esta funcion es mas conservadora que
    `limpiar_precio_pe`: no acepta numeros pelados como precio.
    """
    result = {"precio": None, "moneda": None}
    if not isinstance(texto, str) or not texto.strip():
        return result

    for match in _PRECIO_MONEDA_RE.finditer(texto):
        moneda_raw = match.group("moneda").upper().replace(" ", "")
        moneda = "PEN" if moneda_raw.startswith("S/") else "USD"
        token = _normalizar_token_precio_publicado(match.group("numero"), moneda)
        try:
            precio = float(token.replace(".", "").replace(",", "")) if token else None
        except ValueError:
            precio = None
        if _precio_plausible(precio, moneda):
            return {"precio": precio, "moneda": moneda}

    if match := _PRECIO_ALT_PEN_RE.search(texto):
        token = _normalizar_token_precio_publicado(match.group(1), "PEN")
        try:
            precio = float(token.replace(".", "").replace(",", "")) if token else None
        except ValueError:
            precio = None
        if _precio_plausible(precio, "PEN"):
            return {"precio": precio, "moneda": "PEN"}

    return result
