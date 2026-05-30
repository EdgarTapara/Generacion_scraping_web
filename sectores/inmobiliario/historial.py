"""Adapter del sector inmobiliario sobre `core.historial.HistorialSQLite`.

Declara los campos snapshot que persisten en la tabla `anuncios`. El ciclo
de vida (nuevo/repetido/desaparecido/baja) lo maneja el core.
"""

import pandas as pd

from core.historial import HistorialSQLite


# Columnas snapshot del sector + su tipo SQLite. Incluye:
#  - periodo (anio/trimestre/mes) para agregación trimestral BCRP.
#  - nse para análisis socioeconómico (clasificación por urbanización).
CAMPOS_SNAPSHOT: list[tuple[str, str | None]] = [
    ("posting_id", "TEXT"),
    ("publicacion_id", "TEXT"),
    ("fecha_publicacion", "TEXT"),
    ("anio", "INTEGER"),
    ("trimestre", "TEXT"),
    ("mes", "TEXT"),
    ("titulo", "TEXT"),
    ("tipo_inmueble", "TEXT"),
    ("distrito", "TEXT"),
    ("nse", "TEXT"),
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


def registrar_corrida(
    df: pd.DataFrame,
    portal: str,
    operacion: str,
    ruta_db: str,
    umbral_ausencias: int,
    estado_calidad: str = "ok",
) -> tuple[pd.DataFrame, dict]:
    """Registra una corrida inmobiliaria en el historial SQLite."""
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
