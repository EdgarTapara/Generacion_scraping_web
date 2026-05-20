"""Evaluador de calidad de una corrida.

Patrón heredado de v1/main.py `_evaluar_calidad_scraping`:

* **Umbrales duros por campo** (ej. enlace 99%, precio 70%) que bloquean
  la corrida cuando se incumplen — la marcan como `degradado`.
* **Señales instrumentales** opcionales (ej. "Redux falló en N páginas")
  que generan advertencia pero NO bloquean.
* **Veredicto** estructurado con motivos legibles para el log + decisión
  apta_para_historial.

El sector pasa sus umbrales y señales; este módulo sólo evalúa.

Ejemplo de uso (un sector arma su tabla y delega aquí):

    UMBRALES_INMOBILIARIO = {
        "navent":    {"enlace": 0.99, "precio": 0.70, "distrito": 0.70, "descripcion": 0.50},
        "properati": {"enlace": 0.99, "precio": 0.70, "distrito": 0.70, "descripcion": 0.30},
    }
    veredicto = evaluar_cobertura(
        df,
        umbrales=UMBRALES_INMOBILIARIO.get(estrategia),
        senales_instrumentales=[
            ("Redux DOM match insuficiente", ratio_redux < 0.85),
        ],
    )
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable

import pandas as pd

logger = logging.getLogger("scraping")


class EstadoCalidad(str, Enum):
    OK = "ok"
    ADVERTENCIA = "advertencia"
    DEGRADADO = "degradado"
    SIN_DATOS = "sin_datos"


@dataclass(frozen=True)
class Veredicto:
    estado: EstadoCalidad
    apta_para_historial: bool
    motivos: tuple[str, ...] = field(default_factory=tuple)
    coberturas: dict[str, float] = field(default_factory=dict)

    def loggear(
        self,
        contexto: str,
        logger_: logging.Logger | None = None,
    ) -> None:
        log = logger_ or logger
        msg = " | ".join(self.motivos) if self.motivos else "sin observaciones"
        if self.estado is EstadoCalidad.DEGRADADO:
            log.error("Corrida degradada [%s]: %s", contexto, msg)
        elif self.estado is EstadoCalidad.ADVERTENCIA:
            log.warning("Corrida con advertencias [%s]: %s", contexto, msg)
        elif self.estado is EstadoCalidad.SIN_DATOS:
            log.warning("Sin datos [%s]: %s", contexto, msg)
        else:
            log.info("Corrida OK [%s]", contexto)


def cobertura_por_campo(df: pd.DataFrame, campo: str) -> float:
    """Proporción de filas en las que `campo` está lleno (no nulo y no vacío)."""
    if df is None or df.empty or campo not in df.columns:
        return 0.0
    serie = df[campo]
    no_vacio = serie.notna() & (serie.astype(str).str.strip() != "")
    return float(no_vacio.mean())


def evaluar_cobertura(
    df: pd.DataFrame | None,
    umbrales: dict[str, float] | None = None,
    senales_instrumentales: Iterable[tuple[str, bool]] = (),
) -> Veredicto:
    """Evalúa una corrida.

    Parámetros:
        df: DataFrame de la corrida ya limpiado (no las filas crudas).
        umbrales: dict {campo: cobertura_minima_0_a_1}. Si None o el campo
            no existe, ese campo no genera bloqueo. Cobertura < umbral
            ⇒ estado DEGRADADO.
        senales_instrumentales: lista de (descripción, condición_bool).
            Si la condición es True se registra como advertencia.

    Retorna un `Veredicto`. `apta_para_historial` es False sólo cuando
    el estado es DEGRADADO o SIN_DATOS.
    """
    if df is None or df.empty:
        return Veredicto(
            estado=EstadoCalidad.SIN_DATOS,
            apta_para_historial=False,
            motivos=("No se obtuvieron registros limpios.",),
            coberturas={},
        )

    coberturas: dict[str, float] = {}
    bloqueos: list[str] = []

    for campo, minimo in (umbrales or {}).items():
        cobertura = cobertura_por_campo(df, campo)
        coberturas[campo] = cobertura
        if cobertura < minimo:
            bloqueos.append(
                f"Cobertura de '{campo}' {cobertura:.1%} < umbral {minimo:.0%}"
            )

    advertencias: list[str] = [
        descripcion
        for descripcion, condicion in senales_instrumentales
        if condicion
    ]

    if bloqueos:
        return Veredicto(
            estado=EstadoCalidad.DEGRADADO,
            apta_para_historial=False,
            motivos=tuple(bloqueos + advertencias),
            coberturas=coberturas,
        )
    if advertencias:
        return Veredicto(
            estado=EstadoCalidad.ADVERTENCIA,
            apta_para_historial=True,
            motivos=tuple(advertencias),
            coberturas=coberturas,
        )
    return Veredicto(
        estado=EstadoCalidad.OK,
        apta_para_historial=True,
        motivos=(),
        coberturas=coberturas,
    )
