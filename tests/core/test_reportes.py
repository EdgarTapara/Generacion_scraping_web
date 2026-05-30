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


# -----------------------------
# regeneración desde SQLite
# -----------------------------

def _historial_con_datos(tmp_path):
    from core.historial import HistorialSQLite
    db = str(tmp_path / "h.db")
    h = HistorialSQLite(
        ruta_db=db, sector="demo",
        campos_snapshot=[("precio", "REAL"), ("trimestre", "TEXT")],
        umbral_ausencias=3, campo_operacion="tipo_operacion",
    )
    df = pd.DataFrame({
        "enlace": ["http://x/1", "http://x/2"],
        "tipo_operacion": ["venta", "venta"],
        "precio": [100.0, 200.0],
        "trimestre": ["2026-T1", "2026-T2"],
    })
    h.registrar_corrida(df, "portal_x", "venta", estado_calidad="ok")
    return db


def test_leer_anuncios_sqlite(tmp_path):
    from core.reportes import leer_anuncios_sqlite
    db = _historial_con_datos(tmp_path)
    df = leer_anuncios_sqlite(db, "demo")
    assert len(df) == 2
    assert set(["enlace", "precio", "trimestre"]).issubset(df.columns)
    assert sorted(df["trimestre"]) == ["2026-T1", "2026-T2"]


def test_leer_anuncios_sqlite_bd_inexistente(tmp_path):
    from core.reportes import leer_anuncios_sqlite
    df = leer_anuncios_sqlite(str(tmp_path / "no_existe.db"), "demo")
    assert df.empty


def test_regenerar_excel_desde_sqlite(tmp_path):
    from core.reportes import regenerar_excel_desde_sqlite
    db = _historial_con_datos(tmp_path)
    ruta = str(tmp_path / "consolidado.xlsx")
    out = regenerar_excel_desde_sqlite(db, "demo", ruta, nombre_hoja="Consolidado")
    assert out == ruta
    leida = pd.read_excel(ruta, sheet_name="Consolidado")
    assert len(leida) == 2
    assert "trimestre" in leida.columns


def test_regenerar_excel_sin_datos_no_escribe(tmp_path):
    from core.reportes import regenerar_excel_desde_sqlite
    db = _historial_con_datos(tmp_path)
    ruta = str(tmp_path / "vacio.xlsx")
    out = regenerar_excel_desde_sqlite(db, "sector_inexistente", ruta)
    assert out is None
    assert not (tmp_path / "vacio.xlsx").exists()
