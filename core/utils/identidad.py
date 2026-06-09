"""Generación de `publicacion_id` estable para cualquier sector.

Necesitamos un id que sobreviva entre corridas y entre sectores para
ser clave de cache de IA. Si el portal expone un id propio lo usamos;
si no, derivamos del hash de la URL canonicalizada.

Ejemplos de id resultantes:
    inmobiliario:urbania:alquiler:posting:1234567
    inmobiliario:urbania:alquiler:url:8c2f7a91b3e4d6a0
    empleo:computrabajo:full_time:posting:abc-xyz
"""

from __future__ import annotations

import pandas as pd

from core.utils.enlaces import hash_enlace


def _valor_texto(valor) -> str:
    if valor is None:
        return ""
    try:
        if pd.isna(valor):
            return ""
    except (TypeError, ValueError):
        pass
    return str(valor).strip()


def publicacion_id(
    sector: str,
    portal: str | None,
    operacion: str | None,
    enlace: str | None,
    posting_id: str | None = None,
) -> str:
    """Devuelve un identificador estable.

    Si hay `posting_id` del portal, se usa (más estable y compacto).
    Si no, se usa hash SHA1 truncado del enlace canónico.
    """
    sector_s = _valor_texto(sector).lower() or "sin_sector"
    portal_s = _valor_texto(portal).lower() or "sin_portal"
    operacion_s = _valor_texto(operacion).lower() or "sin_operacion"
    posting = _valor_texto(posting_id)

    if posting:
        return f"{sector_s}:{portal_s}:{operacion_s}:posting:{posting}"
    return f"{sector_s}:{portal_s}:{operacion_s}:url:{hash_enlace(enlace)}"


def asignar_publicacion_id(
    df: pd.DataFrame,
    sector: str,
    columna_portal: str = "portal",
    columna_operacion: str | None = "tipo_operacion",
    columna_posting: str = "posting_id",
    columna_enlace: str = "enlace",
    columna_salida: str = "publicacion_id",
) -> pd.DataFrame:
    """Agrega una columna con `publicacion_id` calculado fila por fila.

    Las columnas no presentes en el DataFrame se tratan como None — útil
    para sectores que no usan operación o que aún no parsean posting_id.
    """
    if df is None or df.empty:
        return df

    out = df.copy()
    ids: list[str] = []
    for _, row in out.iterrows():
        portal = row.get(columna_portal) if columna_portal in out.columns else None
        operacion = (
            row.get(columna_operacion)
            if columna_operacion and columna_operacion in out.columns
            else None
        )
        posting = row.get(columna_posting) if columna_posting in out.columns else None
        enlace = row.get(columna_enlace) if columna_enlace in out.columns else None
        ids.append(publicacion_id(sector, portal, operacion, enlace, posting))

    out[columna_salida] = ids
    return out
