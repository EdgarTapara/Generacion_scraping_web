"""
Exportador Excel acumulativo multi-hoja con deduplicación por claves.

Generaliza el `_merge_historico` de v1/main.py. El contrato:
    - El archivo maestro no lleva fecha en el nombre (una corrida = un append).
    - Cada hoja puede tener claves de dedup distintas.
    - SQLite sigue siendo fuente de verdad; Excel es la vista cómoda.
"""

import logging
import os
from typing import Sequence

import pandas as pd

logger = logging.getLogger("scraping")


class Hoja:
    """Configuración de una hoja del Excel acumulativo."""

    def __init__(
        self,
        nombre: str,
        claves_dedup: Sequence[str],
    ):
        self.nombre = nombre
        self.claves_dedup = list(claves_dedup)


class ExcelAcumulativo:
    """Escribe un Excel con N hojas, haciendo append + dedup sobre lo existente.

    Uso típico:

        exporter = ExcelAcumulativo(
            ruta_archivo="resultados/urbania_alquiler_historico.xlsx",
            hojas=[
                Hoja("Consolidado", ["Enlace", "Fecha de revisión"]),
                Hoja("Diagnostico", ["enlace", "fecha_extraccion"]),
            ],
        )
        exporter.escribir({"Consolidado": df_cons, "Diagnostico": df_diag})
    """

    def __init__(self, ruta_archivo: str, hojas: list[Hoja]):
        self.ruta_archivo = ruta_archivo
        self.hojas = hojas
        self._hojas_por_nombre = {h.nombre: h for h in hojas}

    def _merge(
        self,
        df_nuevo: pd.DataFrame,
        nombre_hoja: str,
        claves_dedup: Sequence[str],
    ) -> pd.DataFrame:
        """Concatena df_nuevo con el contenido previo del archivo en disco."""
        if not os.path.exists(self.ruta_archivo):
            return df_nuevo

        try:
            df_prev = pd.read_excel(self.ruta_archivo, sheet_name=nombre_hoja)
        except Exception as e:
            logger.warning(
                f"No se pudo leer hoja '{nombre_hoja}' de {self.ruta_archivo}: {e}. "
                "Se reescribirá con la corrida actual."
            )
            return df_nuevo

        if df_prev is None or df_prev.empty:
            return df_nuevo

        # Unión de columnas preservando orden del nuevo
        columnas_union = list(df_nuevo.columns) + [
            c for c in df_prev.columns if c not in df_nuevo.columns
        ]
        df_prev = df_prev.reindex(columns=columnas_union)
        df_act = df_nuevo.reindex(columns=columnas_union)

        df_combinado = pd.concat([df_prev, df_act], ignore_index=True)

        claves_existentes = [c for c in claves_dedup if c in df_combinado.columns]
        if claves_existentes:
            df_combinado = df_combinado.drop_duplicates(
                subset=claves_existentes, keep="last"
            ).reset_index(drop=True)
        return df_combinado

    def escribir(self, dataframes: dict[str, pd.DataFrame]) -> str:
        """Merge + escritura. `dataframes` mapea nombre_hoja → df_nuevo.

        Retorna la ruta del archivo escrito.
        """
        os.makedirs(os.path.dirname(self.ruta_archivo) or ".", exist_ok=True)

        combinados: dict[str, pd.DataFrame] = {}
        for hoja in self.hojas:
            df_nuevo = dataframes.get(hoja.nombre, pd.DataFrame())
            combinados[hoja.nombre] = self._merge(
                df_nuevo, hoja.nombre, hoja.claves_dedup
            )

        with pd.ExcelWriter(self.ruta_archivo, engine="openpyxl") as writer:
            for hoja in self.hojas:
                combinados[hoja.nombre].to_excel(
                    writer, sheet_name=hoja.nombre, index=False
                )

        for hoja in self.hojas:
            nuevos = len(dataframes.get(hoja.nombre, pd.DataFrame()))
            total = len(combinados[hoja.nombre])
            logger.info(
                f"Hoja '{hoja.nombre}': +{nuevos} nuevas → {total} totales"
            )
        return self.ruta_archivo
