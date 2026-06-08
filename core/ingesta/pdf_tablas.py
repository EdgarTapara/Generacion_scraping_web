"""Extracción de tablas de PDF, incluidas tablas "complejas" sin bordes.

Aprendizaje (PDFs de fuentes BCRP con cuadros estadísticos): la extracción
lineal de texto destruye las tablas — pega columnas, parte celdas multilínea
y mezcla filas. Las librerías que buscan líneas de borde ("lattice") fallan
cuando la tabla NO tiene rayas y separa columnas sólo con espacios en blanco
("stream"), que es el caso difícil y frecuente.

Estrategia de este módulo, sector-agnóstica:

1. **Lattice** (si hay `pymupdf`): usar `page.find_tables()`, que aprovecha
   las líneas de la grilla cuando existen.
2. **Stream** (fallback robusto, SIN dependencia de bordes): reconstruir la
   tabla desde las coordenadas de cada palabra —
   agrupar por posición vertical en filas y cortar columnas en las bandas de
   espacio en blanco que se repiten entre filas.

El algoritmo de geometría (paso 2) es **puro**: opera sobre cajas de palabras
`(x0, y0, x1, y1, texto)` y no toca el PDF. Por eso se testea con cajas
sintéticas, sin red ni `pymupdf`. El I/O importa `fitz` tarde, igual que
`pdf_columnas`, para que el framework siga instalable sin extras de PDF.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


# Una palabra ubicada: (x0, y0, x1, y1, texto). Coincide con las 5 primeras
# posiciones de lo que devuelve PyMuPDF `page.get_text("words")`.
Palabra = tuple[float, float, float, float, str]


@dataclass(frozen=True)
class TablaExtraida:
    """Una tabla reconstruida: filas de celdas (texto) + metadatos."""

    filas: list[list[str]]
    pagina: int
    metodo: str  # "lattice" | "stream"
    bbox: tuple[float, float, float, float] | None = None

    @property
    def n_filas(self) -> int:
        return len(self.filas)

    @property
    def n_columnas(self) -> int:
        return max((len(f) for f in self.filas), default=0)


def _centro_y(p: Palabra) -> float:
    return (float(p[1]) + float(p[3])) / 2.0


def agrupar_en_filas(
    palabras: Iterable[Palabra],
    *,
    tol_y: float = 3.0,
) -> list[list[Palabra]]:
    """Agrupa palabras en filas por su posición vertical.

    Dos palabras pertenecen a la misma fila si la diferencia entre sus centros
    verticales es ≤ `tol_y` (en puntos PDF). Cada fila sale ordenada por `x0`.
    `tol_y` debe ser menor al interlineado; ~3 pt sirve para cuerpos 8–11 pt.
    """
    ordenadas = sorted(palabras, key=_centro_y)
    filas: list[list[Palabra]] = []
    actual: list[Palabra] = []
    y_ref: float | None = None
    for p in ordenadas:
        cy = _centro_y(p)
        if y_ref is None or abs(cy - y_ref) <= tol_y:
            actual.append(p)
            # promedio móvil simple para que la fila no derive con el ruido
            y_ref = cy if y_ref is None else (y_ref + cy) / 2.0
        else:
            filas.append(sorted(actual, key=lambda w: float(w[0])))
            actual = [p]
            y_ref = cy
    if actual:
        filas.append(sorted(actual, key=lambda w: float(w[0])))
    return filas


def detectar_cortes_columnas(
    palabras: Sequence[Palabra],
    *,
    min_brecha: float = 10.0,
    resolucion: float = 1.0,
) -> list[float]:
    """Detecta los límites de columna como bandas de espacio en blanco.

    Proyecta los intervalos horizontales `[x0, x1]` de TODAS las palabras
    sobre el eje x y busca huecos (zonas que ninguna palabra ocupa) más anchos
    que `min_brecha`. El punto medio de cada hueco es un corte de columna.

    Funciona aunque la tabla no tenga líneas: separa por el blanco consistente
    entre columnas. Devuelve los cortes ordenados (lista vacía = una columna).
    """
    if not palabras:
        return []
    x_min = min(float(p[0]) for p in palabras)
    x_max = max(float(p[2]) for p in palabras)
    if x_max <= x_min:
        return []

    # Marca como ocupada cada celda de la grilla 1D que cubra una palabra.
    n = max(1, int((x_max - x_min) / resolucion) + 1)
    ocupado = [False] * n

    def idx(x: float) -> int:
        return min(n - 1, max(0, int((x - x_min) / resolucion)))

    for p in palabras:
        for i in range(idx(float(p[0])), idx(float(p[2])) + 1):
            ocupado[i] = True

    cortes: list[float] = []
    i = 0
    while i < n:
        if not ocupado[i]:
            j = i
            while j < n and not ocupado[j]:
                j += 1
            ancho = (j - i) * resolucion
            if ancho >= min_brecha:
                centro = x_min + (i + j) / 2.0 * resolucion
                cortes.append(centro)
            i = j
        else:
            i += 1
    return cortes


def _columna_de(p: Palabra, cortes: Sequence[float]) -> int:
    """Índice de columna de una palabra según su centro horizontal."""
    cx = (float(p[0]) + float(p[2])) / 2.0
    col = 0
    for c in cortes:
        if cx > c:
            col += 1
        else:
            break
    return col


def reconstruir_tabla(
    palabras: Sequence[Palabra],
    *,
    tol_y: float = 3.0,
    min_brecha_columna: float = 10.0,
    cortes: Sequence[float] | None = None,
) -> list[list[str]]:
    """Reconstruye una tabla (filas de celdas) desde cajas de palabras.

    Algoritmo "stream", sin dependencia de bordes:
      1. Agrupar palabras en filas por `y` (`agrupar_en_filas`).
      2. Inferir cortes de columna por bandas de blanco (`detectar_cortes_columnas`)
         sobre TODAS las palabras, salvo que se pasen `cortes` explícitos.
      3. Ubicar cada palabra en su columna y unir con espacio las que caen en
         la misma celda (maneja celdas con varias palabras).

    Devuelve `list[list[str]]`. Todas las filas se normalizan al mismo número
    de columnas (celdas faltantes = cadena vacía).
    """
    if not palabras:
        return []
    if cortes is None:
        cortes = detectar_cortes_columnas(palabras, min_brecha=min_brecha_columna)
    n_cols = len(cortes) + 1

    filas_palabras = agrupar_en_filas(palabras, tol_y=tol_y)
    tabla: list[list[str]] = []
    for fila in filas_palabras:
        celdas = ["" for _ in range(n_cols)]
        for p in fila:
            col = _columna_de(p, cortes)
            texto = str(p[4]).strip()
            if not texto:
                continue
            celdas[col] = f"{celdas[col]} {texto}".strip() if celdas[col] else texto
        tabla.append(celdas)
    return tabla


def extraer_tablas_pdf(
    pdf_path: str | Path,
    *,
    estrategia: str = "auto",
    tol_y: float = 3.0,
    min_brecha_columna: float = 10.0,
    paginas: Sequence[int] | None = None,
) -> list[TablaExtraida]:
    """Extrae tablas de un PDF combinando lattice (bordes) y stream (blanco).

    `estrategia`:
      - "auto"    : intenta `find_tables()` (lattice); si una página no devuelve
                    tablas, cae al algoritmo stream sobre sus palabras.
      - "lattice" : sólo `page.find_tables()` (requiere grilla con líneas).
      - "stream"  : sólo reconstrucción por geometría de palabras.

    `paginas` (1-based) limita el barrido; None procesa todas. Requiere
    `pymupdf`; si no está, lanza un error claro sin romper el import del
    framework. La lógica de geometría (`reconstruir_tabla`) es testeable aparte
    sin PDF.
    """
    try:
        import fitz  # type: ignore
    except ImportError as exc:  # pragma: no cover - depende del entorno
        raise RuntimeError("extraer_tablas_pdf requiere pymupdf instalado") from exc

    quiere = set(paginas) if paginas else None
    resultados: list[TablaExtraida] = []
    doc = fitz.open(str(pdf_path))
    try:
        for i in range(doc.page_count):
            num = i + 1
            if quiere is not None and num not in quiere:
                continue
            page = doc[i]

            encontrada_lattice = False
            if estrategia in ("auto", "lattice"):
                try:
                    buscador = page.find_tables()
                    for t in buscador.tables:
                        filas = [
                            [("" if c is None else str(c).strip()) for c in fila]
                            for fila in t.extract()
                        ]
                        if filas:
                            resultados.append(
                                TablaExtraida(
                                    filas=filas, pagina=num, metodo="lattice",
                                    bbox=tuple(t.bbox),
                                )
                            )
                            encontrada_lattice = True
                except Exception:  # find_tables no existe en versiones viejas
                    encontrada_lattice = False

            if estrategia == "lattice":
                continue
            if estrategia == "auto" and encontrada_lattice:
                continue

            palabras = [tuple(w[:5]) for w in page.get_text("words")]
            filas = reconstruir_tabla(
                palabras, tol_y=tol_y, min_brecha_columna=min_brecha_columna
            )
            if filas:
                resultados.append(
                    TablaExtraida(filas=filas, pagina=num, metodo="stream")
                )
    finally:
        doc.close()
    return resultados
