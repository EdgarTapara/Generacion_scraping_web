"""Enriquecimiento con DeepSeek + cache (sector <SECTOR>).

Patrón:
    1. Asignar `publicacion_id` (clave estable cross-corridas).
    2. Aplicar cache: filas con (publicacion_id, descripcion_hash, campo)
       ya cacheadas no se vuelven a consultar.
    3. Fallback regex determinístico (cuando aplique) — barato y rápido.
    4. Sólo los pendientes se mandan a DeepSeek.
    5. Guardar respuestas nuevas en cache para la próxima corrida.

`core.extractor_ia.CachePublicaciones` ya implementa el cache. Aquí
sólo se cablea el prompt y la lectura del payload.
"""

from __future__ import annotations

import json
import logging

import pandas as pd

from core.extractor_ia import CachePublicaciones, DeepSeekExtractor
from core.utils import asignar_publicacion_id

logger = logging.getLogger("scraping")


_SYSTEM_PROMPT = """\
TODO: definir el rol del modelo, qué campo extrae, las REGLAS estrictas
(qué NO devolver, longitud máxima, idioma) y el formato JSON esperado.
"""


def procesar_con_ia(
    df: pd.DataFrame,
    sector: str,
    ruta_cache: str,
    api_key: str,
    modelo_primario: str,
    modelo_secundario: str | None = None,
    campo_objetivo: str = "ubicacion",  # TODO: cambiar
    columna_texto: str = "descripcion",  # TODO: cambiar si el sector usa otro campo
) -> pd.DataFrame:
    """Enriquece el DataFrame con el campo resuelto por IA."""

    df = asignar_publicacion_id(df, sector=sector)

    cache = CachePublicaciones(ruta_cache, columna_texto=columna_texto)
    df = cache.aplicar_a_dataframe(df, campo=campo_objetivo)

    extractor = DeepSeekExtractor(
        api_key=api_key,
        modelo_primario=modelo_primario,
        modelo_secundario=modelo_secundario,
        system_prompt=_SYSTEM_PROMPT,
    )
    if not extractor.disponible():
        logger.info("IA no disponible — quedará lo resuelto por cache/regex.")
        return df

    if campo_objetivo not in df.columns:
        df[campo_objetivo] = None
    mask_pendientes = df[campo_objetivo].isna() | (df[campo_objetivo].astype(str).str.strip() == "")
    pendientes = df[mask_pendientes]
    if pendientes.empty:
        logger.info("Sin pendientes: 100% resuelto por cache/regex.")
        return df

    payload = [
        {
            "id": i,
            "publicacion_id": pendientes.at[idx, "publicacion_id"],
            columna_texto: str(pendientes.at[idx, columna_texto] or "")[:800],
        }
        for i, idx in enumerate(pendientes.index)
    ]

    respuesta = extractor.generar(f"ANUNCIOS:\n{json.dumps(payload, ensure_ascii=False)}")
    if not respuesta:
        return df

    try:
        datos = json.loads(respuesta)
        if isinstance(datos, dict):
            datos = next((v for v in datos.values() if isinstance(v, list)), [])
    except json.JSONDecodeError as exc:
        logger.warning("Respuesta IA no es JSON: %s", exc)
        return df

    mapa = {item.get("id"): item.get(campo_objetivo) for item in datos if isinstance(item, dict)}
    for i, idx in enumerate(pendientes.index):
        valor = mapa.get(i)
        if isinstance(valor, str) and valor.strip():
            df.at[idx, campo_objetivo] = valor.strip()
            cache.guardar(
                publicacion_id=df.at[idx, "publicacion_id"],
                descripcion=df.at[idx, columna_texto],
                campo=campo_objetivo,
                valor=valor.strip(),
                fuente="deepseek",
                modelo=modelo_primario,
            )

    return df
