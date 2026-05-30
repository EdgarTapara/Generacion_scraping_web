"""
Regeneración del Excel consolidado a partir de SQLite.

SQLite es la fuente de verdad longitudinal; el Excel es una vista cómoda.
Si el `.xlsx` se corrompe, se borra por accidente o un analista lo sobre-
escribe, esta utilidad reconstruye el consolidado leyendo la tabla
`anuncios` del historial — sin necesidad de re-scrapear los portales.

No reescribe el snapshot: muestra el último estado conocido de cada
anuncio (lo que vive en SQLite). Para volver a poblar campos que sólo
existían en el Excel previo (y no en el snapshot), hay que re-correr.
"""

from __future__ import annotations

import logging
import os
import sqlite3
from typing import Sequence

import pandas as pd

logger = logging.getLogger("scraping")


def leer_anuncios_sqlite(
    ruta_db: str,
    sector: str,
    *,
    portal: str | None = None,
    campo_operacion: str | None = None,
    operacion: str | None = None,
    solo_activos: bool = False,
    columnas: Sequence[str] | None = None,
) -> pd.DataFrame:
    """Lee la tabla `anuncios` del historial como DataFrame.

    Filtra por `sector` (obligatorio) y opcionalmente por `portal`,
    operación (`campo_operacion` + `operacion`) y `solo_activos` (excluye
    los dados de baja). Devuelve DataFrame vacío si la BD o la tabla no
    existen todavía.
    """
    if not os.path.exists(ruta_db):
        logger.warning("regeneracion: no existe la BD %s", ruta_db)
        return pd.DataFrame()

    where = ['"sector" = ?']
    params: list = [sector]
    if portal:
        where.append('"portal" = ?')
        params.append(portal)
    if campo_operacion and operacion is not None:
        where.append(f'"{campo_operacion}" = ?')
        params.append(operacion)
    if solo_activos:
        where.append('"activo" = 1')

    sql = f'SELECT * FROM "anuncios" WHERE {" AND ".join(where)}'
    try:
        with sqlite3.connect(ruta_db) as conn:
            df = pd.read_sql_query(sql, conn, params=params)
    except (sqlite3.Error, pd.errors.DatabaseError) as exc:
        logger.warning("regeneracion: no se pudo leer anuncios: %s", exc)
        return pd.DataFrame()

    if columnas is not None:
        df = df.reindex(columns=[c for c in columnas if c in df.columns])
    return df


def regenerar_excel_desde_sqlite(
    ruta_db: str,
    sector: str,
    ruta_excel: str,
    *,
    nombre_hoja: str = "Consolidado",
    portal: str | None = None,
    campo_operacion: str | None = None,
    operacion: str | None = None,
    solo_activos: bool = False,
    columnas: Sequence[str] | None = None,
) -> str | None:
    """Reconstruye el Excel consolidado desde SQLite.

    Devuelve la ruta escrita, o None si no había datos que exportar. No
    hace merge con el Excel previo (la intención es justamente regenerar
    cuando el previo se perdió o corrompió); escribe una vista limpia.
    """
    df = leer_anuncios_sqlite(
        ruta_db, sector,
        portal=portal, campo_operacion=campo_operacion, operacion=operacion,
        solo_activos=solo_activos, columnas=columnas,
    )
    if df.empty:
        logger.warning(
            "regeneracion: sin anuncios para sector=%s (no se escribe Excel).",
            sector,
        )
        return None

    os.makedirs(os.path.dirname(ruta_excel) or ".", exist_ok=True)
    with pd.ExcelWriter(ruta_excel, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name=nombre_hoja, index=False)

    logger.info(
        "regeneracion: Excel reconstruido desde SQLite (%d anuncios) → %s",
        len(df), ruta_excel,
    )
    return ruta_excel
