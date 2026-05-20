"""Helpers para extraer y navegar el estado hidratado de SPAs Next.js / Redux.

Metodología validada en v1 (Navent: Urbania + AdondeVivir):

1. Buscar `<script id="__NEXT_DATA__" type="application/json">…</script>` —
   contiene props/initialState/redux state serializado.
2. Si no aparece, hacer fallback regex sobre cualquier blob JSON que
   declare la clave buscada (`listStore.listPostings`, `postingsFeed`, etc.).
3. Recorrer recursivamente el dict hasta encontrar la clave-objetivo.

Por qué no DOM-first: el HTML ya viene renderizado por el SSR pero pierde
estructura — un cambio de clase CSS rompe el parser. El blob JSON es
estable porque sirve para que el cliente hidrate; cambia con releases
mayores del portal, no con cambios visuales.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Iterable

logger = logging.getLogger("scraping")

_RE_NEXT_DATA = re.compile(
    r'<script\s+id="__NEXT_DATA__"\s+type="application/json"\s*>(?P<json>.*?)</script>',
    re.DOTALL,
)


def extraer_next_data(html: str | None) -> dict | None:
    """Devuelve el blob `__NEXT_DATA__` parseado o None.

    No lanza excepciones; un fallo aquí significa que el portal cambió
    su esquema o no es Next.js, y el caller debe hacer fallback a DOM.
    """
    if not html or not isinstance(html, str):
        return None
    match = _RE_NEXT_DATA.search(html)
    if not match:
        return None
    try:
        return json.loads(match.group("json"))
    except json.JSONDecodeError as exc:
        logger.warning("No se pudo parsear __NEXT_DATA__: %s", exc)
        return None


def buscar_clave_recursivo(
    data: Any,
    clave_objetivo: str,
    max_profundidad: int = 30,
) -> Any | None:
    """Búsqueda en profundidad de la primera ocurrencia de `clave_objetivo`.

    Retorna el valor asociado (puede ser dict, list, str, …) o None.
    Útil cuando el portal cambia la ruta exacta dentro del blob pero
    conserva los nombres semánticos (`listPostings`, `postingsFeed`).
    """
    if max_profundidad <= 0:
        return None
    if isinstance(data, dict):
        if clave_objetivo in data:
            return data[clave_objetivo]
        for valor in data.values():
            encontrado = buscar_clave_recursivo(
                valor, clave_objetivo, max_profundidad - 1
            )
            if encontrado is not None:
                return encontrado
    elif isinstance(data, list):
        for item in data:
            encontrado = buscar_clave_recursivo(
                item, clave_objetivo, max_profundidad - 1
            )
            if encontrado is not None:
                return encontrado
    return None


def extraer_redux_state(
    html: str | None,
    claves_objetivo: Iterable[str],
) -> dict[str, Any]:
    """Conveniencia: parsea __NEXT_DATA__ y extrae varias claves a la vez.

    Devuelve un dict {clave: valor} sólo con las que encontró.
    No incluye claves con valor None — facilita chequear cobertura.
    """
    blob = extraer_next_data(html)
    if blob is None:
        return {}
    resultado: dict[str, Any] = {}
    for clave in claves_objetivo:
        valor = buscar_clave_recursivo(blob, clave)
        if valor is not None:
            resultado[clave] = valor
    return resultado
