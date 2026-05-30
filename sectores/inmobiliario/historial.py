"""Adapter del sector inmobiliario sobre `core.historial.HistorialSQLite`.

Declara los campos snapshot que persisten en la tabla `anuncios` (los
mismos que guardaba v1). El resto lo hace el core.
"""

import sqlite3

import pandas as pd

from core.historial import HistorialSQLite
from core.utils import normalizar_enlace


# Columnas snapshot del sector inmobiliario + su tipo SQLite.
CAMPOS_SNAPSHOT: list[tuple[str, str | None]] = [
    ("posting_id", "TEXT"),
    ("publicacion_id", "TEXT"),
    ("fecha_publicacion", "TEXT"),
    # Periodo derivado de fecha_publicacion (agregación trimestral BCRP).
    ("anio", "INTEGER"),
    ("trimestre", "TEXT"),
    ("mes", "TEXT"),
    ("titulo", "TEXT"),
    ("tipo_inmueble", "TEXT"),
    ("distrito", "TEXT"),
    ("precio", "REAL"),
    ("moneda", "TEXT"),
    ("precio_secundario", "REAL"),
    ("moneda_secundaria", "TEXT"),
    ("area_total_m2", "REAL"),
    ("area_construida_m2", "REAL"),
    ("dormitorios", "INTEGER"),
    ("banos", "INTEGER"),
    ("estacionamientos", "INTEGER"),
    ("antiguedad_anos", "INTEGER"),
    ("anunciante", "TEXT"),
    ("precio_por_m2", "REAL"),
    ("latitud", "REAL"),
    ("longitud", "REAL"),
]


def _fecha_desde_primera_vez_visto(valor: str | None) -> str | None:
    if not valor or not isinstance(valor, str):
        return None
    fecha = valor.strip()[:10]
    if len(fecha) == 10 and fecha[4] == "-" and fecha[7] == "-":
        return fecha
    return None


def _fecha_remax_existente(ruta_db: str, enlace: str, operacion: str) -> str | None:
    try:
        with sqlite3.connect(ruta_db) as conn:
            fila = conn.execute(
                'SELECT "fecha_publicacion", "primera_vez_visto" FROM "anuncios" '
                'WHERE "sector" = ? AND "portal" = ? AND "tipo_operacion" = ? '
                'AND "enlace" = ?',
                ("inmobiliario", "remax", operacion, normalizar_enlace(enlace)),
            ).fetchone()
    except sqlite3.Error:
        return None
    if fila is None:
        return None
    return fila[0] or _fecha_desde_primera_vez_visto(fila[1])


def _preparar_fecha_remax(
    df: pd.DataFrame,
    portal: str,
    operacion: str,
    ruta_db: str,
) -> pd.DataFrame:
    if (portal or "").lower().strip() != "remax" or df.empty:
        return df

    df = df.copy()
    if "fecha_publicacion" not in df.columns:
        df["fecha_publicacion"] = None

    fecha_detectada = pd.Timestamp.now().strftime("%Y-%m-%d")
    mask_sin_fecha = df["fecha_publicacion"].isna() | (
        df["fecha_publicacion"].astype(str).str.strip() == ""
    )
    for idx in df[mask_sin_fecha].index:
        df.at[idx, "fecha_publicacion"] = (
            _fecha_remax_existente(ruta_db, df.at[idx, "enlace"], operacion)
            or fecha_detectada
        )
    return df


def registrar_corrida(
    df: pd.DataFrame,
    portal: str,
    operacion: str,
    ruta_db: str,
    umbral_ausencias: int,
    estado_calidad: str = "ok",
) -> tuple[pd.DataFrame, dict]:
    """Registra una corrida inmobiliaria en el historial SQLite."""
    df = _preparar_fecha_remax(df, portal, operacion, ruta_db)
    historial = HistorialSQLite(
        ruta_db=ruta_db,
        sector="inmobiliario",
        campos_snapshot=CAMPOS_SNAPSHOT,
        umbral_ausencias=umbral_ausencias,
        campo_operacion="tipo_operacion",
    )
    return historial.registrar_corrida(
        df,
        portal=portal,
        operacion=operacion,
        estado_calidad=estado_calidad,
    )
