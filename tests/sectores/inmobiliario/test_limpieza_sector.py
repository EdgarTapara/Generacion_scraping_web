"""Tests del pipeline de limpieza + export Alberth."""

import pandas as pd

from sectores.inmobiliario.limpieza import (
    construir_export_alberth,
    construir_titulo,
    pipeline_limpieza,
)


# -----------------------------
# Título estilo Alberth
# -----------------------------

def test_titulo_alquiler_con_distrito():
    t = construir_titulo(
        operacion="alquiler",
        tipo_inmueble="departamento",
        distrito="Cayma",
        moneda="PEN",
        precio=5000.0,
    )
    assert t == "Alquiler apartamento Cayma S/ 5,000"


def test_titulo_venta_con_zone_name_prevale():
    t = construir_titulo(
        operacion="venta",
        tipo_inmueble="casa",
        distrito="Yanahuara",
        moneda="USD",
        precio=250000.0,
        zone_name="Quinta El Chilina",
    )
    assert t == "Venta casa Quinta El Chilina USD 250,000"


def test_titulo_none_si_faltan_campos():
    assert construir_titulo("alquiler", None, "Cayma", "PEN", 5000.0) is None
    assert construir_titulo("alquiler", "casa", "Cayma", "PEN", None) is None


# -----------------------------
# Pipeline completo
# -----------------------------

def test_pipeline_limpieza_datos_completos():
    datos = [{
        "enlace": "https://urbania.pe/dpto/1",
        "posting_id": "149446471",
        "publicacion_id": "urbania:alquiler:posting:149446471",
        "precio": 2500.0,
        "moneda": "PEN",
        "tipo_inmueble": "departamento",
        "distrito": "Cayma",
        "descripcion": "dpto moderno",
        "area_total_m2": 120.0,
        "dormitorios": 3,
        "banos": 2,
        "fecha_extraccion": "2026-04-22",
    }]
    df = pipeline_limpieza(datos, portal="urbania", operacion="alquiler")
    assert len(df) == 1
    row = df.iloc[0]
    assert row["titulo"] == "Alquiler apartamento Cayma S/ 2,500"
    assert row["precio_por_m2"] == round(2500.0 / 120.0, 2)
    assert row["sector"] == "inmobiliario"
    assert row["posting_id"] == "149446471"
    assert row["publicacion_id"] == "urbania:alquiler:posting:149446471"


def test_pipeline_limpieza_dedup_por_enlace():
    datos = [
        {"enlace": "https://x/1", "precio": 100.0, "moneda": "PEN",
         "tipo_inmueble": "departamento", "distrito": "Cayma",
         "fecha_extraccion": "2026-04-22"},
        {"enlace": "https://x/1", "precio": 150.0, "moneda": "PEN",
         "tipo_inmueble": "departamento", "distrito": "Cayma",
         "fecha_extraccion": "2026-04-22"},
    ]
    df = pipeline_limpieza(datos, portal="urbania", operacion="alquiler")
    assert len(df) == 1
    # keep=last → queda 150
    assert df.iloc[0]["precio"] == 150.0


def test_pipeline_fallback_precio_raw_string():
    """Si precio no viene parseado, limpiar_precio_pe debe rescatarlo del raw."""
    datos = [{
        "enlace": "https://x/1",
        "precio_raw": "S/ 1,200",
        "tipo_inmueble": "departamento",
        "distrito": "Cayma",
        "fecha_extraccion": "2026-04-22",
    }]
    df = pipeline_limpieza(datos, portal="urbania", operacion="alquiler")
    assert df.iloc[0]["precio"] == 1200.0
    assert df.iloc[0]["moneda"] == "PEN"


# -----------------------------
# Export institucional (Alberth)
# -----------------------------

def test_export_alberth_filtra_no_residencial():
    df = pd.DataFrame([
        {
            "portal": "urbania", "tipo_operacion": "venta",
            "tipo_inmueble": "departamento", "distrito": "Cayma",
            "titulo": "Venta apartamento Cayma S/ 500,000",
            "precio": 500000.0, "moneda": "PEN",
            "precio_secundario": None, "moneda_secundaria": None,
            "area_total_m2": 100.0, "dormitorios": 3, "banos": 2,
            "estacionamientos": 1, "pisos": 2, "anunciante": "X",
            "enlace": "https://x/1", "ubicacion": None, "address_name": None,
            "fecha_publicacion": "2026-04-22", "fecha_extraccion": "2026-04-22",
            "descripcion": "d",
        },
        {
            "portal": "urbania", "tipo_operacion": "venta",
            "tipo_inmueble": "oficina",  # no residencial → filtrado
            "distrito": "Yanahuara", "titulo": "...", "precio": 100000.0,
            "moneda": "PEN", "precio_secundario": None, "moneda_secundaria": None,
            "area_total_m2": 50.0, "dormitorios": 0, "banos": 1,
            "estacionamientos": 0, "pisos": 1, "anunciante": "Y",
            "enlace": "https://x/2", "ubicacion": None, "address_name": None,
            "fecha_publicacion": "2026-04-22", "fecha_extraccion": "2026-04-22",
            "descripcion": "d",
        },
    ])
    out = construir_export_alberth(df)
    assert len(out) == 1
    assert out.iloc[0]["Tipo"] == "Apartamento"
    assert out.iloc[0]["Fuente"] == "Urbania"


def test_export_alberth_calcula_precio_m2():
    df = pd.DataFrame([{
        "portal": "urbania", "tipo_operacion": "venta",
        "tipo_inmueble": "casa", "distrito": "Cayma",
        "titulo": "Venta casa Cayma USD 200,000",
        "precio": 200000.0, "moneda": "USD",
        "precio_secundario": None, "moneda_secundaria": None,
        "area_total_m2": 100.0, "dormitorios": 3, "banos": 2,
        "estacionamientos": 1, "pisos": 2, "anunciante": "Z",
        "enlace": "https://x/3", "ubicacion": None, "address_name": None,
        "fecha_publicacion": "2026-04-22", "fecha_extraccion": "2026-04-22",
        "descripcion": "d",
    }])
    out = construir_export_alberth(df)
    assert out.iloc[0]["Precio m2 USD"] == 2000.0
    assert out.iloc[0]["Fuente"] == "Urbania"
    # periodo derivado vía core.limpieza.derivar_periodo
    assert out.iloc[0]["Año"] == 2026
    assert out.iloc[0]["Trimestre"] == 2


def test_export_alberth_columnas_orden_esperado():
    """El Excel debe tener exactamente las 23 columnas del modelo Alberth."""
    df = pd.DataFrame([{
        "portal": "urbania", "tipo_operacion": "alquiler",
        "tipo_inmueble": "departamento", "distrito": "Cayma",
        "titulo": "T", "precio": 1000.0, "moneda": "PEN",
        "precio_secundario": None, "moneda_secundaria": None,
        "area_total_m2": 50.0, "dormitorios": 2, "banos": 1,
        "estacionamientos": 0, "pisos": 1, "anunciante": None,
        "enlace": "https://x/1", "ubicacion": None, "address_name": None,
        "fecha_publicacion": "2026-04-22", "fecha_extraccion": "2026-04-22",
        "descripcion": "d",
    }])
    out = construir_export_alberth(df)
    columnas_esperadas = [
        "Fecha", "Año", "Mes", "Trimestre", "Titulos", "Tipo",
        "Distrito", "Localización/Urbanización", "Descripción",
        "Clasificación", "Monto S/", "Monto USD", "Dormitorios", "Baños",
        "Cochera", "Pisos", "m2", "Agencia", "Enlace", "Fecha de revisión",
        "Precio m2 S/", "Precio m2 USD", "Fuente",
    ]
    assert list(out.columns) == columnas_esperadas
    assert len(columnas_esperadas) == 23
