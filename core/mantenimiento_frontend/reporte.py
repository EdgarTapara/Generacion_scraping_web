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
import re
from collections.abc import Iterable, Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

# Pista textual de fallo de red/host inalcanzable (firewall, DNS, portal caído).
# Si aparece, NO es cambio de frontend ni bug de parser: no hay que tocar código.
_PATRON_RED = re.compile(
    r"connecttimeout|connectionerror|read timed out|timed out|max retries|"
    r"failed to establish|newconnectionerror|getaddrinfo|name or service not known|"
    r"connection refused|connection aborted|connection reset|"
    r"sslerror|sslcertverif|proxyerror|nameresolutionerror",
    re.I,
)


def clasificar_fallo(
    *,
    estado: str,
    motivos: list[str] | None,
    diagnostico: dict[str, Any] | None,
    excepcion: str | None,
) -> dict[str, Any]:
    """Clasifica la causa raíz de una corrida fallida.

    El objetivo es que la IA auditora NO revise todo el proyecto en vano: el
    reporte le dice de antemano la categoría del fallo, si es o no un bug de
    código, y qué superficie tocar. Devuelve un dict con ``categoria``,
    ``es_bug_de_codigo``, ``causa``, ``accion`` y ``superficie`` (clave para
    buscar en el mapa ``superficie_por_categoria`` que declara el sector).

    Heurística (orden importa):
        1. RED_O_PORTAL_CAIDO — el host no respondió. No es código.
        2. ANTI_BOT — respondió con desafío/403/429. El parser está bien;
           el portal ahora exige navegador real (escalar a core.browser).
        3. FRONTEND_LISTADO — hubo páginas pero 0 tarjetas (cambió el HTML).
        4. DETALLE — hubo tarjetas pero ningún detalle se extrajo.
        5. COBERTURA_BAJA — hay filas pero faltan campos clave (limpieza).
        6. EXCEPCION — excepción no atribuible a la red.
    """
    motivos = motivos or []
    diag = diagnostico or {}
    texto = " ".join(motivos) + " " + (excepcion or "")

    paginas = int(diag.get("paginas_visitadas") or 0)
    tarjetas = int(diag.get("tarjetas_totales") or 0)
    intentos = int(diag.get("detalle_intentos") or 0)
    exitos = int(diag.get("detalle_exitos") or 0)

    if _PATRON_RED.search(texto):
        return {
            "categoria": "RED_O_PORTAL_CAIDO",
            "es_bug_de_codigo": False,
            "causa": (
                "El host no respondió (timeout de conexión / conexión rechazada / "
                "DNS / SSL). Es bloqueo de red o firewall, o el portal está caído. "
                "NO es un cambio de frontend ni un bug del parser."
            ),
            "accion": (
                "NO modificar el parser ni la limpieza. Relanzar desde una red con "
                "acceso al host (o VPN). Revisar la URL base SOLO si el dominio del "
                "portal cambió de forma permanente."
            ),
            "superficie": "RED",
        }

    if diag.get("anti_bot") or re.search(
        r"\b403\b|\b429\b|forbidden|too many requests|cloudflare|datadome|"
        r"just a moment|captcha|anti-?bot",
        texto, re.I,
    ):
        return {
            "categoria": "ANTI_BOT",
            "es_bug_de_codigo": True,
            "causa": (
                "El portal respondió con un bloqueo anti-bot (Cloudflare/DataDome/"
                "captcha/403/429). El parser está bien: el portal ahora exige un "
                "navegador real con fingerprint humano."
            ),
            "accion": (
                "Escalar a la estrategia de navegador del framework: usar "
                "`core.browser` (undetected-chromedriver) para esta operación en "
                "vez de `core.http`. Ver AGENTS.md → 'HTTP-first y escalado a navegador'."
            ),
            "superficie": "ANTI_BOT",
        }

    if paginas > 0 and tarjetas == 0:
        return {
            "categoria": "FRONTEND_LISTADO",
            "es_bug_de_codigo": True,
            "causa": (
                "El portal respondió (se visitaron páginas) pero el parser no "
                "extrajo ninguna tarjeta. Lo más probable es que el HTML del "
                "listado cambió (clases/estructura) o cambió la fuente embebida."
            ),
            "accion": (
                "Comparar el snapshot HTML capturado contra la fixture vieja y "
                "actualizar SOLO los selectores del parser de listado del portal."
            ),
            "superficie": "LISTADO",
        }

    if tarjetas > 0 and intentos > 0 and exitos == 0:
        return {
            "categoria": "DETALLE",
            "es_bug_de_codigo": True,
            "causa": (
                "El listado funcionó (hay tarjetas) pero la extracción de detalle "
                "falló en todos los casos (página de detalle o su parser)."
            ),
            "accion": (
                "Revisar SOLO la extracción de detalle del portal. No tocar el "
                "parser de listado."
            ),
            "superficie": "DETALLE",
        }

    if re.search(r"cobertura|por debajo|umbral|campo", texto, re.I):
        return {
            "categoria": "COBERTURA_BAJA",
            "es_bug_de_codigo": True,
            "causa": (
                "Se extrajeron filas pero la cobertura de campos clave quedó por "
                "debajo del umbral. Suele ser limpieza/normalización desactualizada."
            ),
            "accion": (
                "Revisar SOLO las reglas deterministas de limpieza/normalización "
                "de los campos con baja cobertura (ver tabla de cobertura)."
            ),
            "superficie": "LIMPIEZA",
        }

    if excepcion:
        return {
            "categoria": "EXCEPCION",
            "es_bug_de_codigo": True,
            "causa": "La corrida lanzó una excepción no atribuible a la red.",
            "accion": (
                "Leer el traceback al final del reporte y reparar el módulo del "
                "portal en el punto exacto que lo lanzó."
            ),
            "superficie": "EXCEPCION",
        }

    return {
        "categoria": "DESCONOCIDO",
        "es_bug_de_codigo": True,
        "causa": "No se pudo clasificar automáticamente la causa.",
        "accion": (
            "Revisar motivos, diagnóstico crudo y snapshots para ubicar la "
            "superficie afectada antes de tocar código."
        ),
        "superficie": "DESCONOCIDO",
    }


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
    superficie_por_categoria: Mapping[str, list[str]] | None = None,
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
        superficie_por_categoria: mapa {superficie: ["archivo: funcion", ...]}
            con la superficie EXACTA a tocar según la categoría del fallo
            (LISTADO, DETALLE, LIMPIEZA, ANTI_BOT, RED, ...). Si está, manda
            sobre `codigo_por_portal`: el reporte dice "tocar SOLO esto".
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

    clasificacion = clasificar_fallo(
        estado=estado, motivos=motivos, diagnostico=diagnostico, excepcion=excepcion,
    )
    if clasificacion["categoria"] == "RED_O_PORTAL_CAIDO":
        prioridad = "P2 - red/infra (no es bug de codigo)"
    else:
        prioridad = _inferir_prioridad(estado, motivos, excepcion)
    cobertura = _cobertura_campos(df, campos_cobertura)
    # Superficie precisa según la categoría del fallo (la declara el sector).
    # Si no hay mapa para la categoría, cae al mapa por portal y, en último
    # caso, a un default genérico.
    superficie = (superficie_por_categoria or {}).get(clasificacion["superficie"])
    codigo = (
        superficie
        or (codigo_por_portal or {}).get(portal)
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
        "## Clasificacion automatica del fallo (lee esto primero)",
        "",
        "Esta seccion existe para ahorrar trabajo: te dice de antemano la causa "
        "probable y si hay que tocar codigo o no. No revises todo el proyecto.",
        "",
        f"- **Categoria**: `{clasificacion['categoria']}`",
        f"- **¿Es bug de codigo?**: "
        f"{'SI' if clasificacion['es_bug_de_codigo'] else 'NO — no toques el codigo'}",
        f"- **Causa probable**: {clasificacion['causa']}",
        f"- **Accion recomendada**: {clasificacion['accion']}",
        "",
        "### Tocar SOLO estos archivos/funciones",
        "",
    ]
    lineas.extend([f"- `{entrada}`" for entrada in codigo])
    lineas.extend([
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
    ])
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
        "0. Si la categoria es `RED_O_PORTAL_CAIDO`, **detente**: no es codigo. "
        "Reporta al tecnico que el host esta inalcanzable y termina.",
        f"1. Contexto minimo: leer {', '.join(f'`{a}`' for a in archivos_lectura_obligada)}.",
        "2. Abrir SOLO los archivos de 'Tocar SOLO estos archivos/funciones' y los "
        "snapshots HTML listados; compararlos contra los fixtures del sector si existen.",
        "3. Confirmar si el fallo viene de frontend, bloqueo anti-bot, datos "
        "embebidos (Redux/__NEXT_DATA__/JSON-LD/XHR), parser local o limpieza.",
        "4. Preferir fuentes estructuradas antes que selectores visuales.",
        "5. Reparar unicamente la superficie indicada por la categoria. No mover "
        "modulos transversales (NSE, IA, SQLite, Excel, `core/`) de lugar.",
        "6. Agregar o actualizar una prueba de regresion con fixture local "
        "antes de correr el portal real.",
        "7. Ejecutar tests del sector. Si pasa, corrida acotada de validacion: "
        "`python -m <mi_proyecto>.main --portal <portal> --paginas 1 --headless`.",
        "8. Documentar el cambio en este reporte y verificar que el historico "
        "longitudinal NO recibio datos contaminados.",
    ])

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
