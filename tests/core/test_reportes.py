"""Tests de `core.reportes.ExcelAcumulativo` (roundtrip con openpyxl)."""

import pandas as pd

from core.reportes import ExcelAcumulativo, Hoja


def _hojas():
    return [Hoja("Hoja1", ["id", "fecha"]), Hoja("Hoja2", ["enlace"])]


def test_escribe_primera_vez_crea_archivo(tmp_path):
    ruta = tmp_path / "salida.xlsx"
    exporter = ExcelAcumulativo(str(ruta), _hojas())
    df1 = pd.DataFrame([{"id": 1, "fecha": "2026-04-22", "valor": "A"}])
    df2 = pd.DataFrame([{"enlace": "https://x.com/1", "precio": 100}])
    exporter.escribir({"Hoja1": df1, "Hoja2": df2})
    assert ruta.exists()

    # Verificar que ambas hojas se persistieron
    leida1 = pd.read_excel(ruta, sheet_name="Hoja1")
    leida2 = pd.read_excel(ruta, sheet_name="Hoja2")
    assert len(leida1) == 1
    assert len(leida2) == 1


def test_append_con_dedup(tmp_path):
    ruta = tmp_path / "salida.xlsx"
    exporter = ExcelAcumulativo(str(ruta), _hojas())

    # Corrida 1: un registro en Hoja1
    exporter.escribir({
        "Hoja1": pd.DataFrame([{"id": 1, "fecha": "2026-04-22", "valor": "viejo"}]),
        "Hoja2": pd.DataFrame(),
    })

    # Corrida 2: un nuevo id=2 + mismo id=1 con valor actualizado
    exporter.escribir({
        "Hoja1": pd.DataFrame([
            {"id": 1, "fecha": "2026-04-22", "valor": "nuevo"},
            {"id": 2, "fecha": "2026-04-22", "valor": "B"},
        ]),
        "Hoja2": pd.DataFrame(),
    })

    resultado = pd.read_excel(ruta, sheet_name="Hoja1")
    # Dedup keep=last → id=1 queda con "nuevo"
    assert len(resultado) == 2
    fila1 = resultado[resultado["id"] == 1].iloc[0]
    assert fila1["valor"] == "nuevo"


def test_dedup_tolera_columnas_faltantes(tmp_path):
    """Cuando la hoja previa no tiene una columna nueva se reconcilia."""
    ruta = tmp_path / "salida.xlsx"
    exporter = ExcelAcumulativo(str(ruta), [Hoja("H", ["id"])])

    exporter.escribir({"H": pd.DataFrame([{"id": 1, "a": "x"}])})
    # Segunda corrida agrega columna "b" nueva
    exporter.escribir({"H": pd.DataFrame([{"id": 2, "a": "y", "b": "z"}])})

    leida = pd.read_excel(ruta, sheet_name="H")
    assert set(["id", "a", "b"]).issubset(leida.columns)
    assert len(leida) == 2
