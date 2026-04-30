"""Enriquecimiento IA inmobiliario con DeepSeek y cache SQLite."""

import hashlib
import json
import logging
import os
import sqlite3
from datetime import datetime
from urllib.parse import urlparse, urlunparse

import pandas as pd

from core.extractor_ia import DeepSeekExtractor
from sectores.inmobiliario.config import (
    DEEPSEEK_API_KEY,
    DEEPSEEK_MODEL,
    DEEPSEEK_MODEL_2,
)
from sectores.inmobiliario.utils_sector import extraer_ubicacion_referencial_regex

logger = logging.getLogger("scraping")

_SYSTEM_PROMPT = """Eres un extractor de referencias urbanas de anuncios inmobiliarios en Arequipa, Peru.

Para cada anuncio, extrae la REFERENCIA URBANA exacta: avenida, calle, jiron, pasaje,
manzana/lote, urbanizacion o referencia a un landmark conocido.

REGLAS ESTRICTAS:
- NO devuelvas el distrito ni "Arequipa" solos.
- NO inventes calles ni nombres que no esten en la descripcion.
- Si solo hay distrito/provincia, devuelve null.
- Si hay multiples referencias, elige la mas especifica.
- Manten la capitalizacion original de los nombres propios.
- Maximo 120 caracteres por referencia.

Responde SOLO con JSON valido: lista de objetos {"id": int, "ubicacion": str|null}."""

_extractor = DeepSeekExtractor(
    api_key=DEEPSEEK_API_KEY,
    modelo_primario=DEEPSEEK_MODEL,
    modelo_secundario=DEEPSEEK_MODEL_2 or None,
    system_prompt=_SYSTEM_PROMPT,
)


def ia_disponible() -> bool:
    return _extractor.disponible()


def _normalizar_enlace_id(enlace: str | None) -> str:
    if not enlace or not isinstance(enlace, str):
        return ""
    p = urlparse(enlace.strip())
    limpio = urlunparse((p.scheme, p.netloc, p.path, "", "", ""))
    return limpio.rstrip("/")


def _valor_texto(valor) -> str:
    if valor is None:
        return ""
    try:
        if pd.isna(valor):
            return ""
    except (TypeError, ValueError):
        pass
    return str(valor).strip()


def _descripcion_hash(descripcion: str | None) -> str:
    texto = _valor_texto(descripcion)
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def asignar_publicacion_id(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega un identificador estable por publicacion para cache y auditoria."""
    if df is None or df.empty:
        return df

    df = df.copy()
    ids = []
    for _, row in df.iterrows():
        portal = _valor_texto(row.get("portal")).lower() or "sin_portal"
        operacion = _valor_texto(row.get("tipo_operacion")).lower() or "sin_operacion"
        posting_id = _valor_texto(row.get("posting_id"))

        if posting_id:
            ids.append(f"{portal}:{operacion}:posting:{posting_id}")
            continue

        enlace = _normalizar_enlace_id(row.get("enlace"))
        digest = hashlib.sha1(enlace.encode("utf-8")).hexdigest()[:16]
        ids.append(f"{portal}:{operacion}:url:{digest}")

    df["publicacion_id"] = ids
    return df


def _inicializar_cache_ia(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ia_ubicaciones (
            publicacion_id TEXT PRIMARY KEY,
            descripcion_hash TEXT NOT NULL,
            ubicacion TEXT,
            fuente TEXT NOT NULL,
            modelo TEXT,
            actualizado_en TEXT NOT NULL
        )
    """)


def _abrir_cache_ia(ruta_cache: str | None):
    if not ruta_cache:
        return None
    carpeta = os.path.dirname(ruta_cache)
    if carpeta:
        os.makedirs(carpeta, exist_ok=True)
    conn = sqlite3.connect(ruta_cache)
    _inicializar_cache_ia(conn)
    return conn


def _aplicar_cache_ubicaciones(df: pd.DataFrame, conn) -> pd.DataFrame:
    if conn is None or "publicacion_id" not in df.columns:
        return df

    for idx, row in df.iterrows():
        if _valor_texto(row.get("ubicacion")):
            continue
        publicacion_id = row.get("publicacion_id")
        cached = conn.execute(
            "SELECT ubicacion FROM ia_ubicaciones "
            "WHERE publicacion_id = ? AND descripcion_hash = ?",
            (publicacion_id, _descripcion_hash(row.get("descripcion"))),
        ).fetchone()
        if cached and cached[0]:
            df.at[idx, "ubicacion"] = cached[0]
    return df


def _guardar_cache_ubicacion(
    conn,
    publicacion_id: str,
    descripcion: str | None,
    ubicacion: str | None,
    fuente: str,
    modelo: str | None = None,
) -> None:
    if conn is None or not publicacion_id or not ubicacion:
        return
    conn.execute(
        "INSERT OR REPLACE INTO ia_ubicaciones "
        "(publicacion_id, descripcion_hash, ubicacion, fuente, modelo, actualizado_en) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            publicacion_id,
            _descripcion_hash(descripcion),
            ubicacion,
            fuente,
            modelo,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ),
    )


def _normalizar_ubicacion(valor, distrito) -> str | None:
    if valor is None or not isinstance(valor, str):
        return None
    v = valor.strip()
    if not v or v.lower() in ("null", "none", "n/a", "na"):
        return None
    if len(v) < 5:
        return None
    if not isinstance(distrito, str):
        distrito = None
    if distrito and v.lower().strip() == distrito.lower().strip():
        return None
    if distrito and v.lower().replace(",", "").strip() in (
        f"{distrito.lower()} arequipa",
        f"{distrito.lower()}",
    ):
        return None
    return v


def _parsear_respuesta_ia(respuesta: str | None) -> list[dict]:
    if not respuesta:
        return []
    try:
        datos = json.loads(respuesta)
    except json.JSONDecodeError:
        return []
    if isinstance(datos, dict):
        datos = next((v for v in datos.values() if isinstance(v, list)), [])
    if not isinstance(datos, list):
        return []
    return [item for item in datos if isinstance(item, dict)]


def extraer_ubicacion_referencial(
    df: pd.DataFrame,
    ruta_cache: str | None = None,
) -> pd.DataFrame:
    """Rellena `ubicacion` con cache, regex determinista y DeepSeek."""
    if "ubicacion" not in df.columns:
        df["ubicacion"] = None
    df = asignar_publicacion_id(df)

    conn_cache = _abrir_cache_ia(ruta_cache)
    try:
        df = _aplicar_cache_ubicaciones(df, conn_cache)

        mask_sin = df["ubicacion"].isna() | (df["ubicacion"] == "")
        if mask_sin.any():
            refs = df.loc[mask_sin, "descripcion"].apply(extraer_ubicacion_referencial_regex)
            mask_regex = mask_sin & refs.notna()
            df.loc[mask_regex, "ubicacion"] = refs.dropna()
            for idx in df[mask_regex].index:
                _guardar_cache_ubicacion(
                    conn_cache,
                    df.at[idx, "publicacion_id"],
                    df.at[idx, "descripcion"],
                    df.at[idx, "ubicacion"],
                    fuente="regex",
                )

        if not _extractor.disponible():
            logger.info("  IA no disponible. Usando cache/regex para ubicacion.")
            return df

        mask_pendientes = df["ubicacion"].isna() | (df["ubicacion"] == "")
        pendientes = df[mask_pendientes]
        if pendientes.empty:
            logger.info("  Ubicacion referencial: 100% resuelto con cache/regex.")
            return df

        indices = pendientes.index.tolist()
        logger.info(f"  Enviando {len(pendientes)} publicaciones nuevas a DeepSeek...")
        payload = []
        for local_id, idx in enumerate(indices):
            payload.append({
                "id": local_id,
                "publicacion_id": df.at[idx, "publicacion_id"],
                "distrito": df.at[idx, "distrito"] or "",
                "descripcion": str(df.at[idx, "descripcion"] or "")[:800],
            })

        prompt = "ANUNCIOS:\n" + json.dumps(payload, ensure_ascii=False)
        mapa = {
            item.get("id"): item.get("ubicacion")
            for item in _parsear_respuesta_ia(_extractor.generar(prompt))
        }
        for local_id, idx in enumerate(indices):
            limpio = _normalizar_ubicacion(mapa.get(local_id), df.at[idx, "distrito"])
            if limpio:
                df.at[idx, "ubicacion"] = limpio
                _guardar_cache_ubicacion(
                    conn_cache,
                    df.at[idx, "publicacion_id"],
                    df.at[idx, "descripcion"],
                    limpio,
                    fuente="deepseek",
                    modelo=DEEPSEEK_MODEL,
                )
    finally:
        if conn_cache is not None:
            conn_cache.commit()
            conn_cache.close()

    return df


def procesar_con_ia(df: pd.DataFrame, ruta_cache: str | None = None) -> pd.DataFrame:
    logger.info("Iniciando enriquecimiento con IA (ubicacion referencial)...")
    df = extraer_ubicacion_referencial(df, ruta_cache=ruta_cache)
    logger.info("Enriquecimiento con IA completado.")
    return df
