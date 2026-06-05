"""Compuerta de calidad: decide si una corrida es apta para actualizar historial.

La metodología nace en v1: una corrida defectuosa NO debe contaminar el
historial longitudinal ni quemar tokens de IA. Si la cobertura de campos
clave cae bajo umbral, la corrida se "degrada" y se exporta aparte para
revisión humana.
"""

from core.calidad.diagnostico import nuevo_diagnostico_scraping
from core.calidad.duplicados import (
    aplicar_resaltado_duplicados,
    detectar_duplicados,
)
from core.calidad.evaluador import (
    EstadoCalidad,
    Veredicto,
    evaluar_cobertura,
    cobertura_por_campo,
)

__all__ = [
    "EstadoCalidad",
    "Veredicto",
    "evaluar_cobertura",
    "cobertura_por_campo",
    "nuevo_diagnostico_scraping",
    "detectar_duplicados",
    "aplicar_resaltado_duplicados",
]
