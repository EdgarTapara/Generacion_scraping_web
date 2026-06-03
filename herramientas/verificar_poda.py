"""Compuerta de poda: detecta módulos sin importadores en un paquete.

Cuando un proyecto standalone adopta metodología del framework, el riesgo es
copiar más de lo que usa y dejar archivos muertos que confunden a quien
revisa el árbol (problema real observado en el scraper de empleo).

Esta herramienta escanea un paquete compartido (p. ej. `<proyecto>/comun/`)
y lista los módulos `.py` que **nadie importa** dentro del proyecto. Es
heurística por análisis de imports (AST), sector-agnóstica y sin red.

Uso:
    python herramientas/verificar_poda.py <ruta_paquete> [--proyecto <raiz>]

Salida: lista de módulos huérfanos. Exit code 1 si hay alguno (sirve como
compuerta en CI o al cerrar una tarea: "no dejes código muerto adentro").
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path


def _modulos_importados(raiz: Path) -> set[str]:
    """Conjunto de nombres dotted importados en cualquier .py bajo `raiz`."""
    importados: set[str] = set()
    for py in raiz.rglob("*.py"):
        try:
            arbol = ast.parse(py.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError, OSError):
            continue
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Import):
                for alias in nodo.names:
                    importados.add(alias.name)
            elif isinstance(nodo, ast.ImportFrom):
                if nodo.module:
                    importados.add(nodo.module)
                    for alias in nodo.names:
                        importados.add(f"{nodo.module}.{alias.name}")
    return importados


def _raiz_proyecto(ruta_paquete: Path) -> Path:
    """Sube mientras el padre siga siendo un paquete (tiene __init__.py)."""
    p = ruta_paquete.resolve()
    while (p.parent / "__init__.py").exists():
        p = p.parent
    return p.parent


def modulos_huerfanos(ruta_paquete: Path, raiz_proyecto: Path | None = None) -> list[Path]:
    """Devuelve los .py del paquete que ningún archivo del proyecto importa.

    Un módulo se considera usado si su nombre dotted (relativo a la raíz del
    proyecto), o un símbolo suyo, aparece en algún import del proyecto. Los
    `__init__.py` se ignoran (son la fachada del paquete, no módulos sueltos).
    """
    ruta_paquete = ruta_paquete.resolve()
    raiz = (raiz_proyecto or _raiz_proyecto(ruta_paquete)).resolve()
    importados = _modulos_importados(raiz)

    huerfanos: list[Path] = []
    for py in sorted(ruta_paquete.rglob("*.py")):
        if py.name == "__init__.py":
            continue
        rel = py.resolve().relative_to(raiz).with_suffix("")
        dotted = ".".join(rel.parts)
        nombre = py.stem
        usado = (
            dotted in importados
            or any(
                i == dotted or i.startswith(dotted + ".") or i.endswith("." + nombre)
                for i in importados
            )
        )
        if not usado:
            huerfanos.append(py)
    return huerfanos


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Detecta módulos sin importadores.")
    parser.add_argument("ruta_paquete", help="Paquete compartido a auditar (ej. comun/).")
    parser.add_argument(
        "--proyecto", default=None,
        help="Raíz del proyecto donde buscar importadores (default: autodetect).",
    )
    args = parser.parse_args(argv)

    ruta_paquete = Path(args.ruta_paquete)
    if not ruta_paquete.is_dir():
        print(f"ERROR: no es un directorio: {ruta_paquete}", file=sys.stderr)
        return 2

    raiz = Path(args.proyecto) if args.proyecto else None
    huerfanos = modulos_huerfanos(ruta_paquete, raiz)

    if not huerfanos:
        print(f"OK: ningún módulo huérfano en {ruta_paquete}.")
        return 0

    print(f"Módulos SIN importadores en {ruta_paquete} (candidatos a borrar):")
    for py in huerfanos:
        print(f"  - {py}")
    print(
        "\nRevisá cada uno: si de verdad nadie lo usa, borralo antes de cerrar "
        "la tarea. No dejes copias muertas de metodología."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
