"""Schema Pydantic del sector <SECTOR>.

Convención: el sector hereda de `core.modelos.AnuncioBase` y añade
campos específicos. NO sobrescribir los campos base.
"""

from __future__ import annotations

from typing import Optional

from pydantic import Field

from core.modelos import AnuncioBase


class AnuncioMiSector(AnuncioBase):  # TODO: renombrar (AnuncioEmpleo, AnuncioFinanciero, ...)
    """Schema principal del anuncio. Sector-específico."""

    # TODO: declarar campos del sector. Ejemplo (empleo):
    #
    # # --- Identificación adicional ---
    # posting_id: Optional[str] = None
    # tipo_operacion: Optional[str] = None
    #
    # # --- Compensación ---
    # salario_minimo: Optional[float] = Field(None, ge=0)
    # salario_maximo: Optional[float] = Field(None, ge=0)
    # moneda: Optional[str] = Field(None, pattern=r"^(PEN|USD)$")
    # modalidad_pago: Optional[str] = None  # mensual / anual / por hora
    #
    # # --- Detalle ---
    # titulo: Optional[str] = None
    # descripcion: Optional[str] = None
    # empresa: Optional[str] = None
    # rubro: Optional[str] = None
    #
    # # --- Ubicación ---
    # distrito: Optional[str] = None
    # ciudad: Optional[str] = None
    # region: Optional[str] = None
    #
    # # --- Calculados / enriquecimientos ---
    # publicacion_id: Optional[str] = None
    # ubicacion: Optional[str] = None
    pass


# Validaciones de negocio (warnings, no excepciones) — el caller las llama
# después de Pydantic y agrega los warnings a la columna `warnings`.
def validar_anuncio(anuncio: AnuncioMiSector) -> list[str]:
    """Devuelve lista de warnings legibles. Vacía si la fila pasa."""
    warnings: list[str] = []
    # TODO: validar reglas específicas (rangos de salario, taxonomías, ...)
    return warnings
