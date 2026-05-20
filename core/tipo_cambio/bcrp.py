"""Cliente del BCRP DataAPI + cache SQLite + conversión auditable.

Metodología (heredada de v1, validada en producción):

* **Fuente**: BCRPData API (`https://estadisticas.bcrp.gob.pe/...`).
  Series diarias del sistema bancario SBS:
    PD04639PD = compra
    PD04640PD = venta
  El BCRP no publica TC en fines de semana ni feriados; no se inventan
  fechas y se usa "fecha anterior más cercana" como fallback.

* **Cache** en SQLite con tabla `tipo_cambio_bcrp`. Una corrida típica
  pide ~7 días y la API responde rápido, pero cuando se reconstruye un
  histórico de meses el cache hace la diferencia.

* **Conversión auditable**: agrega columnas estimadas SIN sobrescribir
  los montos observados. Si una fila ya tiene Monto S/ Y Monto USD
  observados, no se estima nada — se respeta lo del scraper. Si falta
  una y existe la otra, se completa con TC del día y se registra meta:
      TC fecha dato | TC fecha usada | TC compra | TC venta |
      TC usado     | TC fuente      | TC regla

  Esto permite renderizar las celdas estimadas en otro color (ver
  `core.tipo_cambio.formato.marcar_columnas_estimadas_excel`) y dejar
  trazado en el Excel qué se observó y qué se imputó.

El módulo es **sector-agnóstico**: trabaja con DataFrames que tengan
columnas `Monto S/`, `Monto USD` y opcionalmente `m2` (precio por m²
en inmobiliario). Para empleo se podría usar el mismo helper sobre
`Salario S/` / `Salario USD` cambiando los nombres por parámetro.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable, Sequence

import pandas as pd

logger = logging.getLogger("scraping")

# ---------------------------------------------------------------------------
# Configuración por defecto. Sobrescribible via env vars o constructor caller.
# ---------------------------------------------------------------------------

BCRP_API_BASE = "https://estadisticas.bcrp.gob.pe/estadisticas/series/api"
BCRP_TC_FUENTE = (
    "BCRPData API; series PD04639PD compra y PD04640PD venta "
    "TC Sistema bancario SBS (S/ por US$)"
)

SERIE_COMPRA_DEFAULT = "PD04639PD"
SERIE_VENTA_DEFAULT = "PD04640PD"
TIMEOUT_DEFAULT = 20.0
DIAS_MARGEN_DEFAULT = 10
MODO_DEFAULT = "venta"

_MODOS_TC = {"promedio", "compra", "venta"}
_MESES_ES = {
    "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
    "jul": 7, "ago": 8, "set": 9, "sep": 9, "oct": 10, "nov": 11, "dic": 12,
    "jan": 1, "apr": 4, "aug": 8, "dec": 12,
}

# Columnas que aplicar_conversion_tipo_cambio agrega al DataFrame.
COLUMNAS_ESTIMADAS = (
    "Monto S/ estimado TC",
    "Monto USD estimado TC",
    "Precio m2 S/ estimado TC",
    "Precio m2 USD estimado TC",
)
COLUMNAS_AUDITORIA = (
    "TC fecha dato",
    "TC fecha usada",
    "TC compra",
    "TC venta",
    "TC usado",
    "TC fuente",
    "TC regla",
)
COLUMNAS_TC_TODAS = COLUMNAS_ESTIMADAS + COLUMNAS_AUDITORIA


@dataclass(frozen=True)
class TipoCambio:
    fecha: str   # YYYY-MM-DD
    compra: float
    venta: float

    @property
    def promedio(self) -> float:
        return round((self.compra + self.venta) / 2, 6)


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _parse_float(valor) -> float | None:
    if valor is None:
        return None
    try:
        if pd.isna(valor):
            return None
    except (TypeError, ValueError):
        pass
    texto = str(valor).strip()
    if not texto or texto.lower() in {"n.d.", "nd", "nan", "none"}:
        return None
    texto = texto.replace(",", "")
    try:
        return float(texto)
    except ValueError:
        return None


def _parse_periodo_bcrp(nombre: str | None) -> str | None:
    """Convierte un name de periodo BCRP a YYYY-MM-DD (los textos varían)."""
    if not nombre:
        return None
    texto = str(nombre).strip().replace("/", "-")
    directo = pd.to_datetime(texto, errors="coerce", dayfirst=True)
    if pd.notna(directo):
        return directo.strftime("%Y-%m-%d")
    limpio = texto.lower().replace(".", " ").replace("-", " ").replace("_", " ")
    partes = [p for p in limpio.split() if p]
    if len(partes) >= 3:
        try:
            dia = int(partes[0])
            mes = _MESES_ES.get(partes[1][:3])
            anio = int(partes[2])
            if anio < 100:
                anio += 2000 if anio < 80 else 1900
            if mes:
                return datetime(anio, mes, dia).strftime("%Y-%m-%d")
        except ValueError:
            return None
    return None


def _fecha_iso(valor) -> str | None:
    ts = pd.to_datetime(valor, errors="coerce")
    if pd.isna(ts):
        return None
    return ts.strftime("%Y-%m-%d")


def _normalizar_modo(modo: str | None) -> str:
    m = (modo or MODO_DEFAULT).strip().lower()
    if m not in _MODOS_TC:
        raise ValueError(
            f"Modo de tipo de cambio no soportado: {modo!r}. "
            "Usar: promedio, compra o venta."
        )
    return m


def _tc_usado(tc: TipoCambio, modo: str) -> float:
    if modo == "compra":
        return tc.compra
    if modo == "venta":
        return tc.venta
    return tc.promedio


def _regla_texto(modo: str) -> str:
    if modo == "promedio":
        return "promedio simple compra/venta; conversión analítica no tributaria"
    if modo == "compra":
        return "tipo de cambio compra BCRP/SBS"
    return "tipo de cambio venta BCRP/SBS"


# ---------------------------------------------------------------------------
# Descarga
# ---------------------------------------------------------------------------

def descargar_tipo_cambio_bcrp(
    fecha_inicio: str,
    fecha_fin: str,
    serie_compra: str = SERIE_COMPRA_DEFAULT,
    serie_venta: str = SERIE_VENTA_DEFAULT,
    timeout: float = TIMEOUT_DEFAULT,
) -> list[TipoCambio]:
    """Descarga compra/venta diaria. No usa requests para mantener deps mínimas."""
    codigos = f"{serie_compra}-{serie_venta}"
    url = f"{BCRP_API_BASE}/{codigos}/json/{fecha_inicio}/{fecha_fin}/esp"
    req = urllib.request.Request(url, headers={"User-Agent": "bcrp-scraping/core"})

    with urllib.request.urlopen(req, timeout=timeout) as resp:
        texto = resp.read().decode("utf-8", errors="replace").lstrip()
        # BCRPData a veces agrega notices HTML después del JSON válido.
        payload, _ = json.JSONDecoder().raw_decode(texto)

    registros: list[TipoCambio] = []
    for periodo in payload.get("periods", []):
        fecha = _parse_periodo_bcrp(periodo.get("name"))
        values = periodo.get("values") or []
        if not fecha or len(values) < 2:
            continue
        compra = _parse_float(values[0])
        venta = _parse_float(values[1])
        if compra is None or venta is None or compra <= 0 or venta <= 0:
            continue
        registros.append(TipoCambio(fecha=fecha, compra=compra, venta=venta))
    return registros


# ---------------------------------------------------------------------------
# Cache SQLite
# ---------------------------------------------------------------------------

def _crear_tabla_cache(con: sqlite3.Connection, serie_compra: str, serie_venta: str) -> None:
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS tipo_cambio_bcrp (
            fecha TEXT PRIMARY KEY,
            compra REAL NOT NULL,
            venta REAL NOT NULL,
            promedio REAL NOT NULL,
            fuente TEXT NOT NULL,
            series_codigos TEXT NOT NULL,
            descargado_en TEXT NOT NULL
        )
        """
    )
    con.commit()


def _leer_cache(con: sqlite3.Connection) -> dict[str, TipoCambio]:
    rows = con.execute(
        "SELECT fecha, compra, venta FROM tipo_cambio_bcrp"
    ).fetchall()
    return {
        fecha: TipoCambio(fecha=fecha, compra=float(compra), venta=float(venta))
        for fecha, compra, venta in rows
    }


def _guardar_cache(
    con: sqlite3.Connection,
    datos: Iterable[TipoCambio],
    serie_compra: str,
    serie_venta: str,
) -> None:
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rows = [
        (
            tc.fecha,
            tc.compra,
            tc.venta,
            tc.promedio,
            BCRP_TC_FUENTE,
            f"{serie_compra},{serie_venta}",
            ahora,
        )
        for tc in datos
    ]
    if not rows:
        return
    con.executemany(
        """
        INSERT OR REPLACE INTO tipo_cambio_bcrp
            (fecha, compra, venta, promedio, fuente, series_codigos, descargado_en)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    con.commit()


def obtener_tc_por_fecha(
    fechas: Sequence[str],
    ruta_cache: str,
    serie_compra: str = SERIE_COMPRA_DEFAULT,
    serie_venta: str = SERIE_VENTA_DEFAULT,
    dias_margen: int = DIAS_MARGEN_DEFAULT,
    timeout: float = TIMEOUT_DEFAULT,
) -> dict[str, TipoCambio]:
    """Resuelve TC para una lista de fechas, descargando + cacheando si falta.

    Fechas sin dato en BCRP (fin de semana / feriado) caen a la fecha
    anterior más cercana disponible. Si la API falla y no hay cache,
    esa fecha queda sin TC y el caller decide qué hacer.
    """
    if not fechas:
        return {}

    os.makedirs(os.path.dirname(ruta_cache) or ".", exist_ok=True)
    fechas_ordenadas = sorted(set(fechas))
    con = sqlite3.connect(ruta_cache)
    try:
        _crear_tabla_cache(con, serie_compra, serie_venta)
        cache = _leer_cache(con)

        faltan = [f for f in fechas_ordenadas if f not in cache]
        if faltan:
            inicio = (
                pd.to_datetime(min(faltan)) - timedelta(days=dias_margen)
            ).strftime("%Y-%m-%d")
            fin = max(faltan)
            try:
                descargados = descargar_tipo_cambio_bcrp(
                    inicio, fin, serie_compra, serie_venta, timeout
                )
                _guardar_cache(con, descargados, serie_compra, serie_venta)
                cache.update({tc.fecha: tc for tc in descargados})
                logger.info(
                    "Tipo de cambio BCRP: %s registros cacheados (%s a %s).",
                    len(descargados), inicio, fin,
                )
            except Exception as e:
                logger.warning(
                    "No se pudo descargar tipo de cambio BCRP. "
                    "Se usará sólo cache local si existe. Error: %s",
                    e,
                )
    finally:
        con.close()

    disponibles = sorted(cache)
    out: dict[str, TipoCambio] = {}
    for fecha in fechas_ordenadas:
        if fecha in cache:
            out[fecha] = cache[fecha]
            continue
        anteriores = [f for f in disponibles if f <= fecha]
        if anteriores:
            out[fecha] = cache[anteriores[-1]]
    return out


# ---------------------------------------------------------------------------
# Conversión auditable
# ---------------------------------------------------------------------------

def _row_get(row: pd.Series, nombres: tuple[str, ...]):
    for nombre in nombres:
        if nombre in row.index:
            return row.get(nombre)
    return None


def aplicar_conversion_tipo_cambio(
    df: pd.DataFrame,
    ruta_cache: str,
    modo: str = MODO_DEFAULT,
    columna_soles: str = "Monto S/",
    columna_dolares: str = "Monto USD",
    columna_m2: str | None = "m2",
    columnas_fecha: tuple[str, ...] = ("Fecha", "Fecha de revisión"),
    serie_compra: str = SERIE_COMPRA_DEFAULT,
    serie_venta: str = SERIE_VENTA_DEFAULT,
    dias_margen: int = DIAS_MARGEN_DEFAULT,
) -> pd.DataFrame:
    """Agrega columnas estimadas sin modificar montos observados.

    Reglas:
        * Si faltan ambos montos: no se estima nada (no hay base).
        * Si ambos están observados: no se estima nada (se respeta).
        * Si falta uno: se estima usando TC del día.
        * Si hay precio por m² y se estimó el monto, se estima también
          el precio por m² en la otra moneda.

    Las columnas auditoría (`TC fecha dato`, ...) se rellenan siempre
    que se aplicó conversión, para que el lector del Excel pueda
    reconstruir el cálculo.
    """
    if df is None or df.empty:
        return df

    modo = _normalizar_modo(modo)
    out = df.copy()

    for col in COLUMNAS_TC_TODAS:
        if col not in out.columns:
            out[col] = None

    # Recolectar fechas únicas para una sola pasada al cache/API.
    fechas: list[str] = []
    for _, row in out.iterrows():
        soles_ok = pd.notna(row.get(columna_soles)) if columna_soles in out.columns else False
        usd_ok = pd.notna(row.get(columna_dolares)) if columna_dolares in out.columns else False
        if soles_ok and usd_ok:
            continue
        fecha = _fecha_iso(_row_get(row, columnas_fecha))
        if fecha:
            fechas.append(fecha)

    tc_por_fecha = obtener_tc_por_fecha(
        fechas, ruta_cache, serie_compra, serie_venta, dias_margen
    )

    for idx, row in out.iterrows():
        monto_soles = _parse_float(row.get(columna_soles)) if columna_soles in out.columns else None
        monto_usd = _parse_float(row.get(columna_dolares)) if columna_dolares in out.columns else None
        if monto_soles is not None and monto_usd is not None:
            continue
        if monto_soles is None and monto_usd is None:
            continue

        fecha_dato = _fecha_iso(_row_get(row, columnas_fecha))
        if not fecha_dato:
            continue
        tc = tc_por_fecha.get(fecha_dato)
        if not tc:
            continue

        valor_tc = _tc_usado(tc, modo)
        if monto_soles is None and monto_usd is not None:
            out.at[idx, "Monto S/ estimado TC"] = round(monto_usd * valor_tc, 2)
        if monto_usd is None and monto_soles is not None:
            out.at[idx, "Monto USD estimado TC"] = round(monto_soles / valor_tc, 2)

        if columna_m2 and columna_m2 in out.columns:
            m2 = _parse_float(row.get(columna_m2))
            if m2 and m2 > 0:
                est_soles = _parse_float(out.at[idx, "Monto S/ estimado TC"])
                est_usd = _parse_float(out.at[idx, "Monto USD estimado TC"])
                if est_soles is not None:
                    out.at[idx, "Precio m2 S/ estimado TC"] = round(est_soles / m2, 2)
                if est_usd is not None:
                    out.at[idx, "Precio m2 USD estimado TC"] = round(est_usd / m2, 2)

        out.at[idx, "TC fecha dato"] = fecha_dato
        out.at[idx, "TC fecha usada"] = tc.fecha
        out.at[idx, "TC compra"] = tc.compra
        out.at[idx, "TC venta"] = tc.venta
        out.at[idx, "TC usado"] = valor_tc
        out.at[idx, "TC fuente"] = BCRP_TC_FUENTE
        out.at[idx, "TC regla"] = _regla_texto(modo)

    return out


def construir_historial_tc_venta(
    ruta_cache: str,
    fecha_inicio: str,
    fecha_fin: str | None = None,
    serie_compra: str = SERIE_COMPRA_DEFAULT,
    serie_venta: str = SERIE_VENTA_DEFAULT,
) -> pd.DataFrame:
    """Tabla auditable Fecha + TC venta para una hoja del Excel."""
    fecha_fin = fecha_fin or datetime.now().strftime("%Y-%m-%d")

    inicio_ts = pd.to_datetime(fecha_inicio, errors="coerce")
    fin_ts = pd.to_datetime(fecha_fin, errors="coerce")
    if pd.isna(inicio_ts) or pd.isna(fin_ts):
        raise ValueError("fecha_inicio y fecha_fin deben ser fechas válidas.")

    fechas_calendario = pd.date_range(inicio_ts, fin_ts, freq="D")
    fechas = [f.strftime("%Y-%m-%d") for f in fechas_calendario]
    obtener_tc_por_fecha(fechas, ruta_cache, serie_compra, serie_venta)

    con = sqlite3.connect(ruta_cache)
    try:
        cache = _leer_cache(con)
    finally:
        con.close()

    inicio = inicio_ts.strftime("%Y-%m-%d")
    fin = fin_ts.strftime("%Y-%m-%d")
    rows = []
    for fecha in sorted(cache):
        if fecha < inicio or fecha > fin:
            continue
        tc = cache[fecha]
        rows.append({"Fecha TC BCRP": tc.fecha, f"TC SBS Venta {serie_venta}": tc.venta})

    columnas = ["Fecha TC BCRP", f"TC SBS Venta {serie_venta}"]
    return pd.DataFrame(rows, columns=columnas)
