"""Tests de `core.historial.HistorialSQLite`."""

import sqlite3

import pandas as pd

from core.historial import HistorialSQLite


def _hist(ruta_db):
    return HistorialSQLite(
        ruta_db=str(ruta_db),
        sector="test",
        campos_snapshot=[("titulo", "TEXT"), ("precio", "REAL")],
        umbral_ausencias=2,
        campo_operacion="tipo_operacion",
    )


def test_primera_corrida_marca_nuevos(tmp_path):
    hist = _hist(tmp_path / "h.db")
    df = pd.DataFrame([
        {"enlace": "https://x.com/1", "titulo": "Uno", "precio": 100.0},
        {"enlace": "https://x.com/2", "titulo": "Dos", "precio": 200.0},
    ])
    df_out, stats = hist.registrar_corrida(df, portal="urbania", operacion="alquiler")
    assert stats["nuevos"] == 2
    assert stats["repetidos"] == 0
    assert list(df_out["estado_anuncio"]) == ["nuevo", "nuevo"]


def test_segunda_corrida_con_mismo_enlace_marca_repetido(tmp_path):
    hist = _hist(tmp_path / "h.db")
    df1 = pd.DataFrame([{"enlace": "https://x.com/1", "titulo": "V1", "precio": 100.0}])
    hist.registrar_corrida(df1, portal="urbania", operacion="alquiler")

    df2 = pd.DataFrame([{"enlace": "https://x.com/1", "titulo": "V2", "precio": 150.0}])
    df_out, stats = hist.registrar_corrida(df2, portal="urbania", operacion="alquiler")
    assert stats["repetidos"] == 1
    assert stats["nuevos"] == 0
    assert df_out["estado_anuncio"].tolist() == ["repetido"]


def test_desaparicion_incrementa_ausencias_y_da_de_baja(tmp_path):
    hist = _hist(tmp_path / "h.db")
    df1 = pd.DataFrame([
        {"enlace": "https://x.com/1", "titulo": "A", "precio": 10.0},
        {"enlace": "https://x.com/2", "titulo": "B", "precio": 20.0},
    ])
    hist.registrar_corrida(df1, portal="urbania", operacion="alquiler")

    df2 = pd.DataFrame([{"enlace": "https://x.com/1", "titulo": "A", "precio": 10.0}])
    _, stats2 = hist.registrar_corrida(df2, portal="urbania", operacion="alquiler")
    assert stats2["desaparecidos"] == 1
    assert stats2["dados_de_baja"] == 0

    _, stats3 = hist.registrar_corrida(df2, portal="urbania", operacion="alquiler")
    assert stats3["desaparecidos"] == 1
    assert stats3["dados_de_baja"] == 1


def test_bitacora_persiste_corridas(tmp_path):
    hist = _hist(tmp_path / "h.db")
    df = pd.DataFrame([{"enlace": "https://x.com/1", "titulo": "A", "precio": 10.0}])
    hist.registrar_corrida(df, portal="urbania", operacion="alquiler")
    hist.registrar_corrida(df, portal="urbania", operacion="alquiler")
    bitacora = hist.obtener_bitacora()
    assert len(bitacora) == 2
    assert set(bitacora["portal"]) == {"urbania"}


def test_normalizacion_de_enlace_descarta_query_y_fragment(tmp_path):
    hist = _hist(tmp_path / "h.db")
    df1 = pd.DataFrame([{"enlace": "https://x.com/1?utm=a#foo", "titulo": "A", "precio": 10.0}])
    hist.registrar_corrida(df1, portal="urbania", operacion="alquiler")
    df2 = pd.DataFrame([{"enlace": "https://x.com/1?utm=b", "titulo": "A", "precio": 10.0}])
    _, stats = hist.registrar_corrida(df2, portal="urbania", operacion="alquiler")
    assert stats["repetidos"] == 1


def test_corrida_descarta_duplicados_internos(tmp_path):
    hist = _hist(tmp_path / "h.db")
    df = pd.DataFrame([
        {"enlace": "https://x.com/1", "titulo": "Viejo", "precio": 100.0},
        {"enlace": "https://x.com/1", "titulo": "Nuevo", "precio": 150.0},
    ])
    df_out, stats = hist.registrar_corrida(df, portal="urbania", operacion="alquiler")
    assert len(df_out) == 1
    assert stats["nuevos"] == 1
    assert stats["repetidos"] == 0
    assert stats["duplicados_descartados"] == 1
    assert df_out.iloc[0]["titulo"] == "Nuevo"
    assert df_out.iloc[0]["estado_anuncio"] == "nuevo"


def test_mismo_enlace_en_otro_portal_no_colisiona(tmp_path):
    hist = _hist(tmp_path / "h.db")
    df = pd.DataFrame([{"enlace": "https://x.com/1", "titulo": "A", "precio": 10.0}])
    _, stats1 = hist.registrar_corrida(df, portal="urbania", operacion="alquiler")
    _, stats2 = hist.registrar_corrida(df, portal="properati", operacion="alquiler")
    assert stats1["nuevos"] == 1
    assert stats2["nuevos"] == 1
    assert stats2["repetidos"] == 0

    bitacora = hist.obtener_bitacora()
    assert set(bitacora["portal"]) == {"urbania", "properati"}


def test_schema_evoluciona_para_otro_sector_en_misma_db(tmp_path):
    ruta = tmp_path / "h.db"
    hist_inmo = HistorialSQLite(
        ruta_db=str(ruta),
        sector="inmobiliario",
        campos_snapshot=[("titulo", "TEXT")],
        umbral_ausencias=2,
        campo_operacion="tipo_operacion",
    )
    hist_empleo = HistorialSQLite(
        ruta_db=str(ruta),
        sector="empleo",
        campos_snapshot=[("empresa", "TEXT"), ("salario", "REAL")],
        umbral_ausencias=2,
        campo_operacion="rubro",
    )

    df_inmo = pd.DataFrame([{"enlace": "https://x.com/1", "titulo": "Depa"}])
    df_empleo = pd.DataFrame([{
        "enlace": "https://x.com/1",
        "empresa": "BCRP",
        "salario": 5000.0,
    }])

    _, stats_inmo = hist_inmo.registrar_corrida(
        df_inmo, portal="urbania", operacion="alquiler"
    )
    _, stats_empleo = hist_empleo.registrar_corrida(
        df_empleo, portal="computrabajo", operacion="economia"
    )

    assert stats_inmo["nuevos"] == 1
    assert stats_empleo["nuevos"] == 1

    with sqlite3.connect(ruta) as conn:
        columnas = {
            fila[1] for fila in conn.execute('PRAGMA table_info("anuncios")').fetchall()
        }
        assert {
            "id",
            "clave_registro",
            "titulo",
            "tipo_operacion",
            "empresa",
            "salario",
            "rubro",
        } <= columnas

        anuncios = pd.read_sql_query(
            'SELECT sector, portal, enlace FROM "anuncios" ORDER BY sector, portal',
            conn,
        )
        assert len(anuncios) == 2
        assert set(anuncios["sector"]) == {"inmobiliario", "empleo"}


def test_corrida_registra_estado_calidad_en_bitacora(tmp_path):
    hist = _hist(tmp_path / "h.db")
    df = pd.DataFrame([{"enlace": "https://x.com/1", "titulo": "A", "precio": 10.0}])

    hist.registrar_corrida(
        df,
        portal="urbania",
        operacion="alquiler",
        estado_calidad="advertencia",
    )

    bitacora = hist.obtener_bitacora()
    assert bitacora.iloc[0]["estado_calidad"] == "advertencia"


def test_corrida_degradada_no_muta_desaparecidos_por_defecto(tmp_path):
    hist = _hist(tmp_path / "h.db")
    df1 = pd.DataFrame([{"enlace": "https://x.com/1", "titulo": "A", "precio": 10.0}])
    hist.registrar_corrida(df1, portal="urbania", operacion="alquiler")

    df_vacio = pd.DataFrame(columns=["enlace", "titulo", "precio"])
    _, stats = hist.registrar_corrida(
        df_vacio,
        portal="urbania",
        operacion="alquiler",
        estado_calidad="degradado",
    )

    assert stats["desaparecidos"] == 0
    assert stats["mutacion_desaparecidos"] is False
    with sqlite3.connect(tmp_path / "h.db") as conn:
        row = conn.execute(
            'SELECT "ausencias_consecutivas", "activo" FROM "anuncios"'
        ).fetchone()
    assert row == (0, 1)


def test_id_fuente_evita_rerun_idempotente(tmp_path):
    hist = _hist(tmp_path / "h.db")
    df = pd.DataFrame([{"enlace": "https://x.com/1", "titulo": "A", "precio": 10.0}])
    hist.registrar_corrida(
        df,
        portal="urbania",
        operacion="alquiler",
        id_fuente="edicion-2026-05-16",
    )

    df_out, stats = hist.registrar_corrida(
        df,
        portal="urbania",
        operacion="alquiler",
        id_fuente="edicion-2026-05-16",
    )

    assert stats["omitido_por_rerun"] is True
    assert stats["mutacion_desaparecidos"] is False
    assert df_out["estado_anuncio"].tolist() == ["ya_registrado"]
    assert len(hist.obtener_bitacora()) == 1


def test_force_rerun_de_id_fuente_no_marca_ausencias(tmp_path):
    hist = _hist(tmp_path / "h.db")
    df = pd.DataFrame([
        {"enlace": "https://x.com/1", "titulo": "A", "precio": 10.0},
        {"enlace": "https://x.com/2", "titulo": "B", "precio": 20.0},
    ])
    hist.registrar_corrida(
        df,
        portal="urbania",
        operacion="alquiler",
        id_fuente="edicion-2026-05-16",
    )

    df_reproceso = pd.DataFrame([
        {"enlace": "https://x.com/1", "titulo": "A2", "precio": 15.0},
    ])
    _, stats = hist.registrar_corrida(
        df_reproceso,
        portal="urbania",
        operacion="alquiler",
        id_fuente="edicion-2026-05-16",
        permitir_rerun=True,
    )

    assert stats["mutacion_desaparecidos"] is False
    assert stats["desaparecidos"] == 0
    with sqlite3.connect(tmp_path / "h.db") as conn:
        ausencias = conn.execute(
            'SELECT "ausencias_consecutivas" FROM "anuncios" WHERE "enlace"=?',
            ("https://x.com/2",),
        ).fetchone()[0]
    assert ausencias == 0
