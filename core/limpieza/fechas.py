"""
Conversión de fechas relativas / absolutas en español a ISO 8601.

Generaliza v1/limpieza.py:limpiar_fecha. La lógica aplica a cualquier portal
en español peruano (inmobiliario, empleo, etc.) que use frases como
"publicado hace 3 días" o "23 may. 2026".
"""

import re
from datetime import date, datetime, timedelta
from typing import Optional, Sequence


_MESES_ES = {
    "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
    "jul": 7, "ago": 8, "set": 9, "sep": 9, "oct": 10, "nov": 11, "dic": 12,
}


def limpiar_fecha_relativa(
    fecha_raw: str | None,
    referencia: Optional[datetime] = None,
) -> str | None:
    """Convierte fecha relativa o absoluta en español a formato ISO YYYY-MM-DD.

    Ejemplos:
        "Publicado desde ayer"            → referencia - 1 día
        "Publicado hace 3 dias"           → referencia - 3 días
        "Publicado hace 1 semana, 5 dias" → referencia - 12 días
        "Publicado hace 1 hora"           → referencia (< 24 h = hoy)
        "Publicado hoy"                   → referencia
        "Publicado 23 may. 2026"          → "2026-05-23"

    Si `referencia` es None se usa `datetime.now()` (facilita testing pasar
    una fecha fija).
    """
    if not isinstance(fecha_raw, str) or not fecha_raw.strip():
        return None

    texto = fecha_raw.lower().strip()
    hoy = referencia or datetime.now()

    # Fecha absoluta: "23 may. 2026", "6 ene. 2026", "27 mar 2026"
    match = re.search(r"(\d{1,2})\s+([a-z]{3,4})\.?\s+(\d{4})", texto)
    if match:
        dia = int(match.group(1))
        mes_txt = match.group(2)[:3]
        anio = int(match.group(3))
        mes = _MESES_ES.get(mes_txt)
        if mes:
            try:
                return datetime(anio, mes, dia).strftime("%Y-%m-%d")
            except ValueError:
                pass

    if "hoy" in texto:
        return hoy.strftime("%Y-%m-%d")

    if "ayer" in texto:
        return (hoy - timedelta(days=1)).strftime("%Y-%m-%d")

    # "hace N hora[s]" → mismo día
    if re.search(r"hace\s+\d+\s*hora", texto):
        return hoy.strftime("%Y-%m-%d")

    # Combinar semanas + días + meses (granularidad de días)
    total_dias = 0
    encontrado = False

    match = re.search(r"hace\s+(\d+)\s*semanas?", texto)
    if match:
        total_dias += int(match.group(1)) * 7
        encontrado = True

    match = re.search(r"(\d+)\s*d[ií]as?", texto)
    if match and "hace" in texto:
        total_dias += int(match.group(1))
        encontrado = True

    match = re.search(r"hace\s+(\d+)\s*mes(?:es)?", texto)
    if match:
        total_dias += int(match.group(1)) * 30
        encontrado = True

    if encontrado:
        return (hoy - timedelta(days=total_dias)).strftime("%Y-%m-%d")

    return None


# =====================================================================
# Derivación de periodos (mes / trimestre / año) — agregación temporal
# =====================================================================
#
# El BCRP razona en trimestres: casi todo informe macro agrega por
# trimestre y mes. Una vez que un anuncio tiene una fecha limpia
# (`fecha_publicacion` en ISO), conviene materializar columnas de periodo
# para que el Excel y las consultas SQL agrupen sin recalcular fechas.
#
# Convención de formato (ordenable lexicográficamente, sin ambigüedad):
#   anio       -> 2026            (int)
#   mes        -> "2026-05"       (str YYYY-MM)
#   trimestre  -> "2026-T2"       (str YYYY-T{1..4})
#   mes_num    -> 5               (int 1..12)
#   trimestre_num -> 2            (int 1..4)

_PERIODO_CAMPOS = ("anio", "trimestre", "mes", "mes_num", "trimestre_num")
_PERIODO_VACIO = {campo: None for campo in _PERIODO_CAMPOS}

# ISO date / datetime: "2026-05-16", "2026-05-16T08:30:00", "2026/05/16"
_FECHA_ISO_RE = re.compile(r"(\d{4})[-/](\d{1,2})(?:[-/](\d{1,2}))?")


def _coercer_a_date(fecha) -> Optional[date]:
    """Normaliza date/datetime/Timestamp/str ISO a `date`. None si no aplica."""
    if fecha is None:
        return None
    # pandas.Timestamp y datetime exponen .date(); date no.
    if isinstance(fecha, datetime):
        return fecha.date()
    if isinstance(fecha, date):
        return fecha
    # pandas.Timestamp (evita importar pandas aquí): pato-tipado por .date()
    fecha_date = getattr(fecha, "date", None)
    if callable(fecha_date):
        try:
            posible = fecha_date()
            if isinstance(posible, date):
                return posible
        except Exception:
            pass
    if isinstance(fecha, str):
        match = _FECHA_ISO_RE.search(fecha.strip())
        if match:
            anio = int(match.group(1))
            mes = int(match.group(2))
            dia = int(match.group(3)) if match.group(3) else 1
            try:
                return date(anio, mes, dia)
            except ValueError:
                return None
    return None


def derivar_periodo(fecha) -> dict:
    """Deriva columnas de periodo desde una fecha ya limpia.

    Acepta `date`, `datetime`, `pandas.Timestamp` o `str` ISO
    (``YYYY-MM-DD``, también tolera ``YYYY/MM`` o con hora). Devuelve un
    dict con claves ``anio``, ``trimestre``, ``mes``, ``mes_num``,
    ``trimestre_num``. Si la fecha no se puede interpretar, todas son None.

    Ejemplos:
        derivar_periodo("2026-05-16") ->
            {"anio": 2026, "trimestre": "2026-T2", "mes": "2026-05",
             "mes_num": 5, "trimestre_num": 2}
        derivar_periodo(None) -> {todas None}
    """
    dt = _coercer_a_date(fecha)
    if dt is None:
        return dict(_PERIODO_VACIO)
    trimestre_num = (dt.month - 1) // 3 + 1
    return {
        "anio": dt.year,
        "trimestre": f"{dt.year:04d}-T{trimestre_num}",
        "mes": f"{dt.year:04d}-{dt.month:02d}",
        "mes_num": dt.month,
        "trimestre_num": trimestre_num,
    }


def agregar_columnas_periodo(
    df,
    columna_fecha: str = "fecha_publicacion",
    *,
    columnas: Sequence[str] = ("anio", "trimestre", "mes"),
    prefijo: str = "",
):
    """Agrega columnas de periodo a un DataFrame a partir de `columna_fecha`.

    Pensado para correr una sola vez en el pipeline (después de limpiar la
    fecha y antes de exportar): las columnas resultantes fluyen igual al
    Excel y al snapshot de SQLite, de modo que mes/trimestre quedan
    disponibles tanto en la vista cómoda como en consultas SQL.

    Parámetros:
        columna_fecha: nombre de la columna fecha (ISO o date) de origen.
        columnas: qué columnas de periodo materializar y en qué orden.
            Cualquier subconjunto de
            ``{"anio","trimestre","mes","mes_num","trimestre_num"}``.
        prefijo: prefijo opcional para los nombres de columna (ej. para no
            chocar si ya existe `mes`). Por defecto sin prefijo.

    Devuelve el mismo DataFrame (mutado in-place) para encadenar. Si la
    columna fuente no existe, agrega las columnas en None y registra un
    warning — nunca lanza, para no tumbar una corrida por una fecha mala.
    """
    import pandas as pd

    columnas_validas = [c for c in columnas if c in _PERIODO_CAMPOS]
    if not columnas_validas:
        return df

    if columna_fecha not in df.columns:
        import logging

        logging.getLogger("scraping").warning(
            "agregar_columnas_periodo: no existe la columna '%s'; "
            "se agregan columnas de periodo vacías.",
            columna_fecha,
        )
        for campo in columnas_validas:
            df[f"{prefijo}{campo}"] = pd.Series(
                [None] * len(df), index=df.index, dtype=object
            )
        return df

    derivados = [derivar_periodo(v) for v in df[columna_fecha]]
    for campo in columnas_validas:
        # dtype=object preserva int/str/None sin que pandas convierta el año
        # a float (2026.0) cuando hay fechas nulas mezcladas.
        df[f"{prefijo}{campo}"] = pd.Series(
            [d.get(campo) for d in derivados], index=df.index, dtype=object
        )
    return df
