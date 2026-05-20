"""Clasificación NSE por urbanización / lugar con fallback texto-completo.

Metodología (heredada de v1, validada en informe interno BCRP):

* **No usar distrito como clasificación final**: dentro de un distrito
  conviven varios NSE. El distrito SÓLO sirve para desambiguar lugares
  homónimos entre distritos.
* **No usar ML**: la base histórica está muy desbalanceada (87% Alto+Medio
  Alto), entrenar un clasificador produciría sesgo sistemático. Lookup
  por urbanización es auditable y suficiente.
* **No usar geocodificación** mientras las coordenadas tengan baja
  cobertura. Sólo trabajamos con texto (ubicación + zone + address).

El módulo es genérico: acepta cualquier tabla de referencia con columnas
(distrito, lugar, nse) y los textos de normalización (aliases, prefijos
urbanos, vías) son configurables por sector. Los defaults son los de
v1 (Arequipa) por practicidad: si el usuario no cambia nada, funciona.
"""

from core.nse.clasificador import (
    NSEMatch,
    NSEClassifier,
    NSEConfig,
    NSE_CANONICOS,
    extraer_candidatos_urbanizacion,
    asignar_nse_dataframe,
    cargar_clasificador_desde_excel,
)

__all__ = [
    "NSEMatch",
    "NSEClassifier",
    "NSEConfig",
    "NSE_CANONICOS",
    "extraer_candidatos_urbanizacion",
    "asignar_nse_dataframe",
    "cargar_clasificador_desde_excel",
]
