"""Tipo de cambio BCRP para conversión analítica de montos.

Cualquier scraping de precios o salarios en Perú se encuentra con anuncios
en USD que conviene reportar también en PEN (o viceversa). Este módulo
descarga, cachea y aplica el TC del BCRP (series oficiales SBS) sin
modificar los montos observados — sólo agrega columnas estimadas
auditables.

NO usar para cálculos tributarios (sería el TC contable). Es analítico.
"""

from core.tipo_cambio.bcrp import (
    TipoCambio,
    descargar_tipo_cambio_bcrp,
    obtener_tc_por_fecha,
    aplicar_conversion_tipo_cambio,
    construir_historial_tc_venta,
    BCRP_TC_FUENTE,
    COLUMNAS_ESTIMADAS,
    COLUMNAS_AUDITORIA,
    COLUMNAS_TC_TODAS,
)
from core.tipo_cambio.formato import marcar_columnas_estimadas_excel

__all__ = [
    "TipoCambio",
    "descargar_tipo_cambio_bcrp",
    "obtener_tc_por_fecha",
    "aplicar_conversion_tipo_cambio",
    "construir_historial_tc_venta",
    "marcar_columnas_estimadas_excel",
    "BCRP_TC_FUENTE",
    "COLUMNAS_ESTIMADAS",
    "COLUMNAS_AUDITORIA",
    "COLUMNAS_TC_TODAS",
]
