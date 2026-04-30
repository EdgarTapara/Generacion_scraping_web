"""
Pipeline de limpieza del sector inmobiliario.

Reutiliza helpers genéricos de `core.limpieza` (parseo de precio peruano,
fechas relativas) y completa con parsers específicos del sector que viven
en `utils_sector.py`. Conserva la lógica del título "estilo Alberth" y el
export al formato institucional del BCRP.
"""

import logging
import re

import pandas as pd
from pydantic import ValidationError

from core.limpieza import limpiar_fecha_relativa, limpiar_precio_pe, parsear_numero

from sectores.inmobiliario.modelos import (
    AnuncioInmobiliario,
    DISTRITOS_NORM,
    validar_anuncio,
)
from sectores.inmobiliario.utils_sector import (
    detectar_tipo_inmueble_fallback,
    extraer_antiguedad_descripcion,
    extraer_distrito_dom,
    extraer_medio_banos_descripcion,
    extraer_pisos_descripcion,
)

logger = logging.getLogger("scraping")


# =====================================================================
# Helpers locales
# =====================================================================

def limpiar_mantenimiento(mant_raw: str | None) -> float | None:
    """'S/ 120 Mantenimiento' → 120.0"""
    if not isinstance(mant_raw, str) or not mant_raw.strip():
        return None
    numeros = re.findall(r'[\d,]+', mant_raw)
    if numeros:
        try:
            return float(numeros[0].replace(",", ""))
        except ValueError:
            return None
    return None


# =====================================================================
# Construcción del título "estilo Alberth"
# =====================================================================

_TIPO_INMUEBLE_LEGIBLE = {
    "departamento": "apartamento",
    "casa": "casa",
    "local_comercial": "local comercial",
    "terreno": "terreno",
    "oficina": "oficina",
    "habitacion": "habitacion",
    "otro": "inmueble",
}

_MONEDA_SIMBOLO = {"PEN": "S/", "USD": "USD"}


def _formatear_precio(precio: float | None) -> str | None:
    if precio is None:
        return None
    try:
        return f"{int(round(float(precio))):,}"
    except (ValueError, TypeError):
        return None


def construir_titulo(
    operacion: str,
    tipo_inmueble: str | None,
    distrito: str | None,
    moneda: str | None,
    precio: float | None,
    zone_name: str | None = None,
) -> str | None:
    """'Alquiler apartamento Cayma S/ 5,000'. Prefiere zone_name sobre distrito."""
    lugar = zone_name if zone_name else distrito
    if not operacion or tipo_inmueble is None or not lugar or not moneda or precio is None:
        return None

    tipo_legible = _TIPO_INMUEBLE_LEGIBLE.get(tipo_inmueble, tipo_inmueble)
    simbolo = _MONEDA_SIMBOLO.get(moneda, moneda)
    precio_fmt = _formatear_precio(precio)
    if not precio_fmt:
        return None

    return f"{operacion.capitalize()} {tipo_legible} {lugar} {simbolo} {precio_fmt}"


# =====================================================================
# Pipeline principal
# =====================================================================

def pipeline_limpieza(
    datos_crudos: list[dict], portal: str, operacion: str
) -> pd.DataFrame:
    """Datos crudos del scraper → DataFrame tipado y validado.

    Los datos ya vienen pre-rellenados desde el Redux state en el scraper
    (para portales Navent); aquí se normalizan, se corren fallbacks desde
    descripción, se construye el título estilo Alberth y se valida con
    Pydantic + reglas de negocio.
    """
    if not datos_crudos:
        return pd.DataFrame()

    logger.info(f"Limpiando {len(datos_crudos)} registros...")

    registros_limpios = []
    errores = 0
    warnings_totales: list[str] = []

    for raw in datos_crudos:
        # --- Precio ---
        precio = raw.get("precio")
        moneda = raw.get("moneda")
        precio_sec = raw.get("precio_secundario")
        moneda_sec = raw.get("moneda_secundaria")

        if precio is None and raw.get("precio_raw"):
            precio_data = limpiar_precio_pe(raw.get("precio_raw"))
            precio = precio_data["precio"]
            moneda = precio_data["moneda"]
            precio_sec = precio_data["precio_secundario"]
            moneda_sec = precio_data["moneda_secundaria"]

        # --- Mantenimiento ---
        mantenimiento = raw.get("mantenimiento")
        if mantenimiento is None and raw.get("mantenimiento_raw"):
            mantenimiento = limpiar_mantenimiento(raw.get("mantenimiento_raw"))

        # --- Tipo de inmueble ---
        tipo_inmueble = raw.get("tipo_inmueble")
        if not tipo_inmueble:
            tipo_inmueble = detectar_tipo_inmueble_fallback(
                descripcion=raw.get("descripcion"),
                enlace=raw.get("enlace"),
            )

        # --- Medio baños ---
        medio_banos = extraer_medio_banos_descripcion(raw.get("descripcion"))

        # --- Antigüedad ---
        antiguedad = raw.get("antiguedad_anos")
        if antiguedad is None:
            antiguedad = extraer_antiguedad_descripcion(raw.get("descripcion"))

        # --- Pisos ---
        pisos = raw.get("pisos")
        if pisos is None:
            pisos = extraer_pisos_descripcion(raw.get("descripcion"))

        # --- Distrito ---
        distrito = raw.get("distrito")
        if not distrito:
            distrito = extraer_distrito_dom(raw.get("ubicacion_raw"), DISTRITOS_NORM)

        zone_name = raw.get("zone_name")
        address_name = raw.get("address_name")

        # --- Título Alberth ---
        titulo = construir_titulo(
            operacion=operacion,
            tipo_inmueble=tipo_inmueble,
            distrito=distrito,
            moneda=moneda,
            precio=precio,
            zone_name=zone_name,
        )

        # --- Fecha publicación ---
        fecha_pub = raw.get("fecha_publicacion") or limpiar_fecha_relativa(
            raw.get("fecha_publicacion_raw")
        )

        registro = {
            "enlace": raw.get("enlace", ""),
            "portal": portal,
            "sector": "inmobiliario",
            "tipo_operacion": operacion,
            "posting_id": raw.get("posting_id"),
            "publicacion_id": raw.get("publicacion_id"),
            "precio_raw": raw.get("precio_raw"),
            "precio": precio,
            "moneda": moneda,
            "precio_secundario": precio_sec,
            "moneda_secundaria": moneda_sec,
            "mantenimiento_raw": raw.get("mantenimiento_raw"),
            "mantenimiento": mantenimiento,
            "fecha_publicacion_raw": raw.get("fecha_publicacion_raw"),
            "fecha_publicacion": fecha_pub,
            "titulo": titulo,
            "tipo_inmueble": tipo_inmueble,
            "descripcion": raw.get("descripcion"),
            "distrito": distrito,
            "zone_name": zone_name,
            "address_name": address_name,
            "ubicacion": None,  # lo rellena extractor_ia
            "area_total_m2": raw.get("area_total_m2"),
            "area_construida_m2": raw.get("area_construida_m2"),
            "dormitorios": raw.get("dormitorios"),
            "banos": raw.get("banos"),
            "medio_banos": medio_banos,
            "estacionamientos": raw.get("estacionamientos"),
            "pisos": pisos,
            "antiguedad_anos": antiguedad,
            "anunciante": raw.get("anunciante") or raw.get("anunciante_dom"),
            "fecha_extraccion": raw.get("fecha_extraccion"),
            "precio_por_m2": None,
            "warnings": "",
        }

        # Validar con Pydantic y aplicar reglas de negocio en un solo paso
        try:
            anuncio = AnuncioInmobiliario(**registro)
        except ValidationError as e:
            errores += 1
            registro["warnings"] = f"Error de validacion: {e.error_count()} campos"
            registro_validado = registro
        else:
            ws = validar_anuncio(anuncio)
            registro_validado = anuncio.model_dump()
            if ws:
                registro_validado["warnings"] = "; ".join(ws)
                warnings_totales.extend(ws)

        # Derivados
        precio_v = registro_validado.get("precio")
        area_v = registro_validado.get("area_total_m2")
        if precio_v and area_v and area_v > 0:
            registro_validado["precio_por_m2"] = round(precio_v / area_v, 2)

        registros_limpios.append(registro_validado)

    df = pd.DataFrame(registros_limpios)

    # Dedup por enlace
    antes = len(df)
    df = df.drop_duplicates(subset=["enlace"], keep="last")
    duplicados = antes - len(df)
    if duplicados > 0:
        logger.info(f"  Eliminados {duplicados} duplicados")

    logger.info(f"  Registros limpios: {len(df)}")
    logger.info(f"  Errores de validacion: {errores}")
    for campo in [
        "distrito", "zone_name", "area_total_m2", "area_construida_m2",
        "dormitorios", "banos", "medio_banos", "estacionamientos", "pisos",
        "antiguedad_anos", "precio", "anunciante", "titulo",
    ]:
        if campo in df.columns:
            llenos = df[campo].notna().sum()
            pct = llenos * 100 // len(df) if len(df) else 0
            logger.info(f"  {campo}: {llenos}/{len(df)} ({pct}%)")
    if warnings_totales:
        logger.info(f"  Warnings de negocio: {len(warnings_totales)}")
        for w in warnings_totales[:5]:
            logger.info(f"    - {w}")

    return df


# =====================================================================
# Export al formato institucional "Alberth" (hoja Consolidado)
# =====================================================================

_TIPO_CONSOLIDADO = {
    "departamento": "Apartamento",
    "casa": "Casa",
    "terreno": "Terreno",
    "local_comercial": "Local Comercial",
    "oficina": "Oficina",
    "habitacion": "Habitacion",
    "otro": "Inmueble",
}

_TIPOS_RESIDENCIALES = {"departamento", "casa", "terreno", "habitacion"}

_FUENTE_LEGIBLE = {
    "urbania": "Urbania",
    "adondevivir": "A donde vivir",
    "properati": "Properati",
    "remax": "RE/MAX",
}


def _split_monto_por_moneda(
    precio: float | None,
    moneda: str | None,
    precio_sec: float | None,
    moneda_sec: str | None,
) -> dict:
    out = {"monto_soles": None, "monto_usd": None}
    for monto, mon in ((precio, moneda), (precio_sec, moneda_sec)):
        if monto is None or not mon:
            continue
        try:
            v = float(monto)
        except (TypeError, ValueError):
            continue
        if v <= 0:
            continue
        if mon == "PEN" and out["monto_soles"] is None:
            out["monto_soles"] = v
        elif mon == "USD" and out["monto_usd"] is None:
            out["monto_usd"] = v
    return out


def _derivar_anio_mes_trimestre(fecha: str | None) -> tuple:
    if not fecha or not isinstance(fecha, str):
        return (None, None, None)
    try:
        ts = pd.to_datetime(fecha, errors="coerce")
    except Exception:
        return (None, None, None)
    if pd.isna(ts):
        return (None, None, None)
    trimestre = (ts.month - 1) // 3 + 1
    return (int(ts.year), int(ts.month), int(trimestre))


def construir_export_alberth(df: pd.DataFrame) -> pd.DataFrame:
    """DataFrame interno → esquema 23 columnas del archivo institucional.

    Filtra a segmento residencial (departamento/casa/terreno/habitacion).
    """
    if df is None or df.empty:
        return pd.DataFrame()

    filas = []
    for _, r in df.iterrows():
        tipo_raw = r.get("tipo_inmueble")
        if tipo_raw not in _TIPOS_RESIDENCIALES:
            continue

        fecha = r.get("fecha_publicacion")
        anio, mes, trimestre = _derivar_anio_mes_trimestre(fecha)

        tipo = _TIPO_CONSOLIDADO.get(
            tipo_raw, tipo_raw.title() if isinstance(tipo_raw, str) else None
        )

        montos = _split_monto_por_moneda(
            r.get("precio"), r.get("moneda"),
            r.get("precio_secundario"), r.get("moneda_secundaria"),
        )

        m2 = r.get("area_total_m2")
        try:
            m2_num = float(m2) if m2 is not None and not pd.isna(m2) else None
        except (TypeError, ValueError):
            m2_num = None

        precio_m2_soles = None
        precio_m2_usd = None
        if m2_num and m2_num > 0:
            if montos["monto_soles"] is not None:
                precio_m2_soles = round(montos["monto_soles"] / m2_num, 2)
            if montos["monto_usd"] is not None:
                precio_m2_usd = round(montos["monto_usd"] / m2_num, 2)

        portal = (r.get("portal") or "").lower().strip()
        fuente = _FUENTE_LEGIBLE.get(portal, portal.title() if portal else None)

        localizacion = r.get("ubicacion") or r.get("address_name") or None

        ts_fecha = pd.to_datetime(fecha, errors="coerce") if fecha else pd.NaT
        fecha_solo = ts_fecha.date() if pd.notna(ts_fecha) else None

        fecha_rev_raw = r.get("fecha_extraccion")
        ts_rev = pd.to_datetime(fecha_rev_raw, errors="coerce") if fecha_rev_raw else pd.NaT
        fecha_rev_solo = ts_rev.date() if pd.notna(ts_rev) else None

        filas.append({
            "Fecha": fecha_solo,
            "Año": anio,
            "Mes": mes,
            "Trimestre": trimestre,
            "Titulos": r.get("titulo"),
            "Tipo": tipo,
            "Distrito": r.get("distrito"),
            "Localización/Urbanización": localizacion,
            "Descripción": r.get("descripcion"),
            "Clasificación": None,
            "Monto S/": montos["monto_soles"],
            "Monto USD": montos["monto_usd"],
            "Dormitorios": r.get("dormitorios"),
            "Baños": r.get("banos"),
            "Cochera": r.get("estacionamientos"),
            "Pisos": r.get("pisos"),
            "m2": m2_num,
            "Agencia": r.get("anunciante"),
            "Enlace": r.get("enlace"),
            "Fecha de revisión": fecha_rev_solo,
            "Precio m2 S/": precio_m2_soles,
            "Precio m2 USD": precio_m2_usd,
            "Fuente": fuente,
        })

    columnas = [
        "Fecha", "Año", "Mes", "Trimestre", "Titulos", "Tipo",
        "Distrito", "Localización/Urbanización", "Descripción",
        "Clasificación", "Monto S/", "Monto USD", "Dormitorios", "Baños",
        "Cochera", "Pisos", "m2", "Agencia", "Enlace", "Fecha de revisión",
        "Precio m2 S/", "Precio m2 USD", "Fuente",
    ]
    return pd.DataFrame(filas, columns=columnas)
