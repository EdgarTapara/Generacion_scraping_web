"""Generador de reportes Markdown para cambios de frontend.

Patrón heredado de v1/mantenimiento_frontend.py (validado en producción).

El sector llama a `generar_reporte_mantenimiento_frontend(...)` cuando una
corrida queda degradada / sin datos / con excepción. El reporte:

1. Resume estado, motivos, prioridad inferida.
2. Tabula cobertura de campos clave para la corrida fallida.
3. Pega el diagnóstico estructurado como JSON.
4. Lista los snapshots HTML capturados (rutas + url + bytes).
5. Da instrucciones específicas a la IA auditora con los archivos del
   sector donde mirar (parametrizado por `codigo_por_portal`).

La IDEA central: la IA que recibe el reporte no necesita reproducir la
corrida — tiene toda la evidencia que el scraper vio en su momento.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterable, Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


def _valor_serializable(valor: Any) -> Any:
    """JSON-encode tolerante: convierte a str lo que no es serializable nativo."""
    if isinstance(valor, (str, int, float, bool)) or valor is None:
        return valor
    if isinstance(valor, (list, tuple)):
        return [_valor_serializable(v) for v in valor]
    if isinstance(valor, dict):
        return {str(k): _valor_serializable(v) for k, v in valor.items()}
    return str(valor)


def _cobertura_campos(
    df: pd.DataFrame | None,
    campos: Iterable[str],
) -> list[dict[str, Any]]:
    """Calcula % no-vacío por campo. Util para identificar qué se perdió."""
    if df is None or df.empty:
        return []
    total = len(df)
    out: list[dict[str, Any]] = []
    for campo in campos:
        if campo not in df.columns:
            out.append({
                "campo": campo, "llenos": 0, "total": total,
                "pct": 0.0, "presente": False,
            })
            continue
        serie = df[campo]
        llenos = int((serie.notna() & (serie.astype(str).str.strip() != "")).sum())
        out.append({
            "campo": campo,
            "llenos": llenos,
            "total": total,
            "pct": round(llenos / total, 4) if total else 0.0,
            "presente": True,
        })
    return out


def _inferir_prioridad(estado: str, motivos: list[str], excepcion: str | None) -> str:
    texto = " ".join(motivos).lower()
    if excepcion:
        return "P0 - excepcion en corrida"
    if estado in {"sin_datos", "error"}:
        return "P0 - portal sin datos utiles"
    if "enlace" in texto or "no se obtuvieron" in texto:
        return "P0 - identidad longitudinal en riesgo"
    return "P1 - extraccion degradada"


def _snapshots_desde_diagnostico(diagnostico: dict[str, Any]) -> list[dict[str, Any]]:
    snapshots = diagnostico.get("snapshots_html") or []
    if not isinstance(snapshots, list):
        return []
    return [s for s in snapshots if isinstance(s, dict) and s.get("archivo")]


CAMPOS_COBERTURA_DEFAULT = (
    "enlace",
    "precio",
    "distrito",
    "descripcion",
    "ubicacion",
    "area_total_m2",
    "anunciante",
)


def generar_reporte_mantenimiento_frontend(
    *,
    portal: str,
    operacion: str | None,
    estado: str,
    carpeta_reportes: str | os.PathLike[str],
    motivos: list[str] | None = None,
    diagnostico: dict[str, Any] | None = None,
    df: pd.DataFrame | None = None,
    ruta_degradada: str | None = None,
    excepcion: str | None = None,
    codigo_por_portal: Mapping[str, list[str]] | None = None,
    archivos_lectura_obligada: Iterable[str] = (
        "AGENTS.md",
        "main.py",
        "scraper.py",
        "limpieza.py",
        "modelos.py",
    ),
    campos_cobertura: Iterable[str] = CAMPOS_COBERTURA_DEFAULT,
    reglas_inviolables: Iterable[str] = (
        "Las corridas degradadas no entran al historico.",
        "Flujo vigente: scraping -> limpieza -> publicacion_id -> compuerta de calidad -> IA -> SQLite -> Excel.",
        "Preferir fuentes estructuradas (Redux/__NEXT_DATA__/JSON/XHR) antes que selectores visuales.",
        "No relajar umbrales para que una corrida pase; primero demostrar que el dato sigue siendo correcto.",
    ),
) -> str:
    """Escribe un reporte Markdown auditable. Retorna la ruta del archivo creado.

    Parámetros:
        portal, operacion, estado: identifican la corrida fallida.
        carpeta_reportes: directorio destino. Se crea si no existe.
        motivos: lista de razones (del veredicto de calidad).
        diagnostico: dict producido por `nuevo_diagnostico_scraping` con
            snapshots_html y métricas por etapa.
        df: DataFrame de la corrida (post-limpieza) para calcular cobertura.
        ruta_degradada: ruta al Excel que se exportó a `degradadas/`.
        excepcion: traceback string si la corrida lanzó.
        codigo_por_portal: mapa {portal: ["archivo: funcion", ...]} con
            las funciones del sector donde buscar la causa. El sector
            lo declara — `core/` no lo conoce.
        archivos_lectura_obligada: archivos del sector que la IA auditora
            debe leer antes de proponer un cambio. Defaults a los típicos.
        campos_cobertura: qué campos tabular en la sección cobertura.
        reglas_inviolables: convenciones del proyecto que el reporte
            recuerda al final. El sector puede sobrescribirlas.
    """
    motivos = motivos or []
    diagnostico = diagnostico or {}
    sello = datetime.now().strftime("%Y%m%d_%H%M%S")
    carpeta = Path(carpeta_reportes)
    carpeta.mkdir(parents=True, exist_ok=True)
    nombre = f"{portal}_{operacion or 'sin_op'}_{estado}_frontend_{sello}.md"
    ruta = carpeta / nombre

    prioridad = _inferir_prioridad(estado, motivos, excepcion)
    cobertura = _cobertura_campos(df, campos_cobertura)
    codigo = (
        (codigo_por_portal or {}).get(portal)
        or [
            "<sector>/portal_scrapers/<portal>.py",
            "<sector>/scraper.py",
            "<sector>/limpieza.py",
        ]
    )
    snapshots = _snapshots_desde_diagnostico(diagnostico)
    diagnostico_json = json.dumps(
        _valor_serializable(diagnostico),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )

    lineas: list[str] = [
        f"# Reporte de mantenimiento frontend - {portal}/{operacion or '-'}",
        "",
        f"- Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- Estado detectado: `{estado}`",
        f"- Prioridad sugerida: {prioridad}",
        f"- Archivo degradado asociado: `{ruta_degradada or '-'}`",
        "",
        "## Diagnostico operativo",
        "",
        "Este reporte se genera cuando la corrida no debe asumirse como normal. "
        "Puede significar cambio de frontend, bloqueo del portal, fallo de parser, "
        "cambio en datos embebidos o una regresion local. No actualizar SQLite ni "
        "Excel maestro hasta cerrar la causa.",
        "",
        "### Motivos",
        "",
    ]
    lineas.extend([f"- {m}" for m in motivos] or ["- Sin motivos detallados capturados."])

    lineas.extend([
        "",
        "### Cobertura de campos",
        "",
        "| campo | llenos | total | pct | presente |",
        "|---|---:|---:|---:|---|",
    ])
    if cobertura:
        for item in cobertura:
            lineas.append(
                f"| {item['campo']} | {item['llenos']} | {item['total']} | "
                f"{item['pct']:.1%} | {item['presente']} |"
            )
    else:
        lineas.append("| - | 0 | 0 | 0.0% | False |")

    lineas.extend([
        "",
        "### Diagnostico tecnico crudo",
        "",
        "```json",
        diagnostico_json,
        "```",
        "",
        "### Snapshots HTML capturados",
        "",
    ])
    if snapshots:
        lineas.extend([
            "| pagina | etapa | bytes | archivo |",
            "|---:|---|---:|---|",
        ])
        for item in snapshots:
            lineas.append(
                f"| {item.get('pagina', '-')} | {item.get('etapa', '-')} | "
                f"{item.get('bytes', '-')} | `{item.get('archivo')}` |"
            )
    else:
        lineas.append("- No se capturo snapshot HTML en esta corrida.")

    lineas.extend([
        "",
        "## Instrucciones para la IA auditora",
        "",
        f"1. Leer primero {', '.join(f'`{a}`' for a in archivos_lectura_obligada)}.",
        "2. Abrir los snapshots HTML listados arriba y compararlos contra los "
        "fixtures/manuales del sector si existen.",
        "3. Confirmar si el fallo viene de frontend, bloqueo anti-bot, datos "
        "embebidos (Redux/__NEXT_DATA__/XHR), parser local o limpieza posterior.",
        "4. Preferir fuentes estructuradas antes que selectores visuales.",
        "5. Cambiar solo el parser/selectores del portal afectado. No mover "
        "modulos transversales (NSE, IA, SQLite, Excel) de lugar.",
        "6. Agregar o actualizar una prueba de regresion con fixture local "
        "antes de correr el portal real.",
        "7. Ejecutar tests del sector. Si pasa, corrida acotada de validacion: "
        "`python -m sectores.<sector>.main --portal <portal> --paginas 1 --headless`.",
        "8. Documentar el cambio en este reporte y verificar que el historico "
        "longitudinal NO recibio datos contaminados.",
        "",
        "## Archivos y funciones probables",
        "",
    ])
    lineas.extend([f"- `{entrada}`" for entrada in codigo])

    lineas.extend([
        "",
        "## Reglas que no se deben romper",
        "",
    ])
    lineas.extend([f"- {r}" for r in reglas_inviolables])

    if excepcion:
        lineas.extend([
            "",
            "## Excepcion capturada",
            "",
            "```text",
            excepcion.strip(),
            "```",
        ])

    lineas.append("")
    ruta.write_text("\n".join(lineas), encoding="utf-8")
    return str(ruta)
