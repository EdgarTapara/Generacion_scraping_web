import re

from core.ingesta import PaginaTexto, ordenar_bloques_texto, segmentar_documento


CODIGO_RE = re.compile(
    r"([BFVC]\d{3}-\d{7,12}(?:-\d+)?\s*/\s*(?:S|E[-\s]?)\d{1,2})\s*/?\s*",
    re.IGNORECASE,
)
SECCION_RE = re.compile(r"/\s*(S|E[-\s]?)(\d{1,2})", re.IGNORECASE)


def test_ordena_bloques_por_columna_y_y():
    blocks = [
        (100, 20, 120, 30, "col2-y20", 0, 0),
        (0, 30, 20, 40, "col1-y30", 0, 0),
        (0, 10, 20, 20, "col1-y10", 0, 0),
        (0, 0, 20, 10, "imagen", 0, 1),
    ]

    assert ordenar_bloques_texto(blocks, ancho_columna=50) == [
        "col1-y10",
        "col1-y30",
        "col2-y20",
    ]


def test_segmenta_documento_y_filtra_secciones_objetivo():
    paginas = [
        PaginaTexto(
            pagina=1,
            texto=(
                "SE ALQUILA departamento Cercado 999999999 B014-0000048098/S2 "
                "AUTO usado buen estado B014-0000048099/S7 "
                "SE VENDE casa Cayma B014-0000048100/E-3"
            ),
        )
    ]

    avisos = segmentar_documento(
        paginas,
        codigo_regex=CODIGO_RE,
        seccion_regex=SECCION_RE,
        secciones_objetivo={"S2", "E3"},
    )

    assert [a.codigo for a in avisos] == ["B014-0000048098/S2", "B014-0000048100/E-3"]
    assert [a.seccion for a in avisos] == ["S2", "E3"]
    assert "AUTO usado" not in " ".join(a.texto for a in avisos)
