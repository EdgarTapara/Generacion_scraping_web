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
