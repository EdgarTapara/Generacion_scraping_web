"""Tests del algoritmo de reconstrucción de tablas (geometría pura, sin PDF).

Se usan cajas de palabras sintéticas `(x0, y0, x1, y1, texto)` para simular lo
que PyMuPDF devolvería en `page.get_text("words")`, sin abrir ningún PDF ni
depender de pymupdf.
"""

from core.ingesta import (
    agrupar_en_filas,
    detectar_cortes_columnas,
    reconstruir_tabla,
)


def _tabla_sin_bordes():
    """3 columnas separadas por blanco, 2 filas de datos + encabezado.

    Layout (x aproximado):
        Region(10)        Empleos(120)     Var(220)
        Arequipa(10)      1500(120)        3.2(220)
        Lima(10)          8000(120)        1.1(220)
    """
    def w(x, y, texto, ancho=40):
        return (x, y, x + ancho, y + 8, texto)

    return [
        w(10, 10, "Region"), w(120, 10, "Empleos"), w(220, 10, "Var"),
        w(10, 30, "Arequipa"), w(120, 30, "1500"), w(220, 30, "3.2"),
        w(10, 50, "Lima"), w(120, 50, "8000"), w(220, 50, "1.1"),
    ]


def test_agrupa_filas_por_y():
    filas = agrupar_en_filas(_tabla_sin_bordes(), tol_y=3.0)
    assert len(filas) == 3
    # cada fila tiene 3 palabras, ordenadas por x
    for fila in filas:
        assert len(fila) == 3
        xs = [p[0] for p in fila]
        assert xs == sorted(xs)


def test_detecta_tres_columnas():
    cortes = detectar_cortes_columnas(_tabla_sin_bordes(), min_brecha=10.0)
    # 3 columnas -> 2 cortes
    assert len(cortes) == 2


def test_reconstruye_tabla_sin_bordes():
    tabla = reconstruir_tabla(_tabla_sin_bordes(), tol_y=3.0, min_brecha_columna=10.0)
    assert tabla == [
        ["Region", "Empleos", "Var"],
        ["Arequipa", "1500", "3.2"],
        ["Lima", "8000", "1.1"],
    ]


def test_celda_multipalabra_se_une():
    """Una celda con dos palabras ('San Isidro') debe quedar junta en su columna."""
    def w(x, y, texto, ancho=40):
        return (x, y, x + ancho, y + 8, texto)

    palabras = [
        w(10, 10, "Distrito"), w(220, 10, "NSE"),
        w(10, 30, "San", ancho=25), w(40, 30, "Isidro", ancho=35), w(220, 30, "A"),
    ]
    tabla = reconstruir_tabla(palabras, tol_y=3.0, min_brecha_columna=10.0)
    assert tabla[0] == ["Distrito", "NSE"]
    assert tabla[1] == ["San Isidro", "A"]


def test_cortes_explicitos_respetan_columnas():
    tabla = reconstruir_tabla(_tabla_sin_bordes(), cortes=[80.0, 180.0])
    assert tabla[1] == ["Arequipa", "1500", "3.2"]


def test_entrada_vacia():
    assert reconstruir_tabla([]) == []
    assert detectar_cortes_columnas([]) == []
    assert agrupar_en_filas([]) == []


def test_una_sola_columna_no_inventa_cortes():
    def w(x, y, texto, ancho=40):
        return (x, y, x + ancho, y + 8, texto)

    palabras = [w(10, 10, "Total"), w(10, 30, "Subtotal"), w(10, 50, "Suma")]
    cortes = detectar_cortes_columnas(palabras, min_brecha=10.0)
    assert cortes == []
    tabla = reconstruir_tabla(palabras)
    assert tabla == [["Total"], ["Subtotal"], ["Suma"]]
