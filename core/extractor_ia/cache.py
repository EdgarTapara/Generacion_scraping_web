"""Cache SQLite para respuestas de IA, clave (publicacion_id, descripcion_hash).

Sin esta capa cada corrida re-procesaría cada anuncio aunque su contenido
no haya cambiado, quemando tokens de DeepSeek (o cualquier otro
proveedor) en valde.

Esquema:
    Tabla `ia_respuestas`
        publicacion_id   TEXT   PK  — id estable cross-corridas
        descripcion_hash TEXT   PK  — sha256 del texto normalizado
        campo            TEXT   PK  — qué campo se resolvió (p.ej. 'ubicacion')
        valor            TEXT       — respuesta del modelo
        fuente           TEXT       — 'regex' | 'deepseek' | 'gemini' | ...
        modelo           TEXT       — id del modelo concreto
        actualizado_en   TEXT       — timestamp ISO

La PK compuesta permite que un mismo anuncio tenga varios campos cacheados
en filas distintas (sector empleo puede pedir 'rubro' + 'modalidad';
sector inmobiliario 'ubicacion' + 'tipo_inmueble_inferido').

Si la descripción cambia se reescribe el hash y la fila vieja queda
huérfana; ocupa unos bytes y no afecta la lógica de hits.
"""

from __future__ import annotations

import logging
import os
import sqlite3
from datetime import datetime
from typing import Iterable

import pandas as pd

from core.utils.texto import descripcion_hash

logger = logging.getLogger("scraping")


class CachePublicaciones:
    """Wrapper sobre SQLite con API simple para look-up por publicación.

    El caller decide qué columna del DataFrame es el texto a hashear
    (en inmobiliario es `descripcion`; en empleo podría ser `requisitos`).
    """

    def __init__(self, ruta_db: str, columna_texto: str = "descripcion"):
        self.ruta_db = ruta_db
        self.columna_texto = columna_texto
        os.makedirs(os.path.dirname(ruta_db) or ".", exist_ok=True)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.ruta_db)
        self._inicializar(conn)
        return conn

    def _inicializar(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ia_respuestas (
                publicacion_id   TEXT NOT NULL,
                descripcion_hash TEXT NOT NULL,
                campo            TEXT NOT NULL,
                valor            TEXT,
                fuente           TEXT NOT NULL,
                modelo           TEXT,
                actualizado_en   TEXT NOT NULL,
                PRIMARY KEY (publicacion_id, descripcion_hash, campo)
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ia_respuestas_pub_campo "
            "ON ia_respuestas (publicacion_id, campo)"
        )

    # -----------------------------------------------------------------
    # Lookup / guardado
    # -----------------------------------------------------------------

    def lookup(
        self,
        publicacion_id: str,
        descripcion: str | None,
        campo: str,
    ) -> str | None:
        if not publicacion_id:
            return None
        with self._conn() as conn:
            row = conn.execute(
                "SELECT valor FROM ia_respuestas "
                "WHERE publicacion_id = ? AND descripcion_hash = ? AND campo = ?",
                (publicacion_id, descripcion_hash(descripcion), campo),
            ).fetchone()
        if row and row[0] is not None and str(row[0]).strip():
            return row[0]
        return None

    def guardar(
        self,
        publicacion_id: str,
        descripcion: str | None,
        campo: str,
        valor: str | None,
        fuente: str,
        modelo: str | None = None,
    ) -> None:
        if not publicacion_id or not valor:
            return
        ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO ia_respuestas "
                "(publicacion_id, descripcion_hash, campo, valor, fuente, modelo, actualizado_en) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    publicacion_id,
                    descripcion_hash(descripcion),
                    campo,
                    valor,
                    fuente,
                    modelo,
                    ahora,
                ),
            )

    # -----------------------------------------------------------------
    # Aplicación a DataFrames
    # -----------------------------------------------------------------

    def aplicar_a_dataframe(
        self,
        df: pd.DataFrame,
        campo: str,
        columna_destino: str | None = None,
        columna_publicacion_id: str = "publicacion_id",
    ) -> pd.DataFrame:
        """Rellena `columna_destino` con valores cacheados donde aplique.

        Sólo toca filas en las que la columna destino está vacía: si el
        scraper ya resolvió el valor de otra fuente, no se sobrescribe.
        """
        destino = columna_destino or campo
        if df is None or df.empty or columna_publicacion_id not in df.columns:
            return df
        if destino not in df.columns:
            df[destino] = None

        with self._conn() as conn:
            for idx, row in df.iterrows():
                actual = row.get(destino)
                if isinstance(actual, str) and actual.strip():
                    continue
                pub_id = row.get(columna_publicacion_id)
                if not pub_id:
                    continue
                texto = row.get(self.columna_texto)
                cached = conn.execute(
                    "SELECT valor FROM ia_respuestas "
                    "WHERE publicacion_id = ? AND descripcion_hash = ? AND campo = ?",
                    (pub_id, descripcion_hash(texto), campo),
                ).fetchone()
                if cached and cached[0]:
                    df.at[idx, destino] = cached[0]
        return df

    def guardar_dataframe(
        self,
        df: pd.DataFrame,
        campo: str,
        columna_valor: str,
        fuente: str,
        modelo: str | None = None,
        columna_publicacion_id: str = "publicacion_id",
        solo_indices: Iterable[int] | None = None,
    ) -> int:
        """Guarda todas las (publicacion_id, descripcion_hash, campo→valor) de un DF.

        `solo_indices` permite restringir a las filas recién resueltas para
        no reescribir innecesariamente las que ya estaban cacheadas.
        Retorna cuántas filas se guardaron.
        """
        if df is None or df.empty:
            return 0
        if columna_publicacion_id not in df.columns or columna_valor not in df.columns:
            return 0

        ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        indices = list(solo_indices) if solo_indices is not None else df.index.tolist()
        filas: list[tuple] = []
        for idx in indices:
            if idx not in df.index:
                continue
            row = df.loc[idx]
            pub_id = row.get(columna_publicacion_id)
            valor = row.get(columna_valor)
            if not pub_id or not isinstance(valor, str) or not valor.strip():
                continue
            filas.append(
                (
                    pub_id,
                    descripcion_hash(row.get(self.columna_texto)),
                    campo,
                    valor,
                    fuente,
                    modelo,
                    ahora,
                )
            )

        if not filas:
            return 0

        with self._conn() as conn:
            conn.executemany(
                "INSERT OR REPLACE INTO ia_respuestas "
                "(publicacion_id, descripcion_hash, campo, valor, fuente, modelo, actualizado_en) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                filas,
            )
        return len(filas)
