"""Extracción de estado embebido en SPAs (Next.js __NEXT_DATA__, similar).

Muchos portales modernos hidratan la página con un blob JSON. Aprovecharlo
da mucho más detalle que parsear el DOM y es resiliente a cambios visuales.

El módulo es **genérico**: no conoce campos de un sector concreto. Cada
sector usa estos helpers y luego mapea claves específicas (CFT codes,
postingLocation, priceOperationTypes, etc.) en sus propios helpers.
"""

from core.redux.parser import (
    extraer_next_data,
    buscar_clave_recursivo,
    extraer_redux_state,
)

__all__ = [
    "extraer_next_data",
    "buscar_clave_recursivo",
    "extraer_redux_state",
]
