"""
Enriquecimiento IA para el sector inmobiliario.

Delega en `core.extractor_ia.GeminiExtractor` (fallback dual-API) y aplica
el prompt específico del sector: extracción de la referencia urbana
(Av./Calle/Jr./Mz./Urb.) desde la descripción del anuncio.

Migrado de v1/extractor_ia.py; la lógica retry / dual-API subió a core,
este archivo contiene solo lo específico de inmobiliario.
"""

import json
import logging
import hashlib
import time
from urllib.parse import urlparse, urlunparse

import pandas as pd

from core.extractor_ia import GeminiExtractor
from sectores.inmobiliario.config import (
    GEMINI_API_KEY, GEMINI_MODEL, GEMINI_API_KEY_2, GEMINI_MODEL_2,
)
from sectores.inmobiliario.utils_sector import extraer_ubicacion_referencial_regex

logger = logging.getLogger("scraping")

# Extractor singleton — se crea al importar y se reutiliza en cada llamada
_extractor = GeminiExtractor(
    api_key_primaria=GEMINI_API_KEY,
    modelo_primario=GEMINI_MODEL,
    api_key_secundaria=GEMINI_API_KEY_2 or None,
    modelo_secundario=GEMINI_MODEL_2 or None,
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


def _normalizar_ubicacion_gemini(valor, distrito) -> str | None:
    """Filtra valores que Gemini puede devolver erróneamente (distrito solo,
    cadenas muy cortas, 'null' literal, etc.)."""
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
        f"{distrito.lower()} arequipa", f"{distrito.lower()}",
    ):
        return None
    return v


def extraer_ubicacion_referencial(df: pd.DataFrame) -> pd.DataFrame:
    """Rellena la columna `ubicacion` con una referencia urbana.

    Fase 1: regex determinista vectorizado (barato).
    Fase 2: Gemini batch para los que quedaron sin ubicación.
    """
    if "ubicacion" not in df.columns:
        df["ubicacion"] = None

    # Fase 1 — fallback regex
    mask_sin = df["ubicacion"].isna() | (df["ubicacion"] == "")
    if mask_sin.any():
        refs = df.loc[mask_sin, "descripcion"].apply(extraer_ubicacion_referencial_regex)
        df.loc[mask_sin & refs.notna(), "ubicacion"] = refs.dropna()

    if not _extractor.disponible():
        logger.info("  IA no disponible. Usando solo regex para ubicacion.")
        return df

    # Fase 2 — Gemini batch
    mask_pendientes = df["ubicacion"].isna() | (df["ubicacion"] == "")
    pendientes = df[mask_pendientes]
    if pendientes.empty:
        logger.info("  Ubicacion referencial: 100% resuelto con regex.")
        return df

    logger.info(
        f"  Enviando {len(pendientes)} descripciones a Gemini para ubicacion referencial..."
    )

    TAMANO_LOTE = 20
    indices_list = pendientes.index.tolist()

    prompt_base = (
        "Eres un extractor de referencias urbanas de anuncios inmobiliarios "
        "en Arequipa, Peru.\n\n"
        "Para cada anuncio, extrae la REFERENCIA URBANA exacta: avenida, "
        "calle, jiron, pasaje, manzana/lote, urbanizacion o referencia a un "
        "landmark conocido (ej. 'a 2 cuadras del Real Plaza').\n\n"
        "REGLAS ESTRICTAS:\n"
        "- NO devuelvas el distrito ni 'Arequipa' solos.\n"
        "- NO inventes calles ni nombres que no esten en la descripcion.\n"
        "- Si solo hay distrito/provincia, devuelve null.\n"
        "- Si hay multiples referencias, elige la mas especifica.\n"
        "- Mantén la capitalizacion original de los nombres propios.\n"
        "- Maximo 120 caracteres.\n\n"
        "Responde SOLO con JSON valido: lista de objetos "
        '{"id": int, "ubicacion": str|null}.\n\n'
        "ANUNCIOS:\n"
    )

    for batch_start in range(0, len(indices_list), TAMANO_LOTE):
        batch_idxs = indices_list[batch_start:batch_start + TAMANO_LOTE]

        payload = []
        for local_id, idx in enumerate(batch_idxs):
            desc = df.at[idx, "descripcion"] or ""
            distrito_row = df.at[idx, "distrito"] or ""
            payload.append({
                "id": local_id,
                "distrito": distrito_row,
                "descripcion": str(desc)[:800],
            })

        prompt = prompt_base + json.dumps(payload, ensure_ascii=False)
        respuesta = _extractor.generar(prompt)
        if respuesta:
            try:
                datos = json.loads(respuesta)
                if isinstance(datos, list):
                    mapa = {
                        item.get("id"): item.get("ubicacion")
                        for item in datos if isinstance(item, dict)
                    }
                    for local_id, idx in enumerate(batch_idxs):
                        valor = mapa.get(local_id)
                        distrito_row = df.at[idx, "distrito"]
                        limpio = _normalizar_ubicacion_gemini(valor, distrito_row)
                        if limpio:
                            df.at[idx, "ubicacion"] = limpio
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Error parseando respuesta de Gemini: {e}")

        if batch_start + TAMANO_LOTE < len(indices_list):
            time.sleep(2)

    return df


def procesar_con_ia(df: pd.DataFrame) -> pd.DataFrame:
    logger.info("Iniciando enriquecimiento con IA (ubicacion referencial)...")
    df = extraer_ubicacion_referencial(df)
    logger.info("Enriquecimiento con IA completado.")
    return df
