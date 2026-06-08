"""Tests de la compuerta de poda (core/poda.py)."""

from core.poda import modulos_huerfanos


def _crear_proyecto(tmp_path):
    """Proyecto mínimo: paquete `comun` con un módulo usado y uno huérfano."""
    proyecto = tmp_path / "proyecto"
    comun = proyecto / "comun"
    comun.mkdir(parents=True)
    (proyecto / "__init__.py").write_text("", encoding="utf-8")
    (comun / "__init__.py").write_text("", encoding="utf-8")
    (comun / "usado.py").write_text("VALOR = 1\n", encoding="utf-8")
    (comun / "huerfano.py").write_text("OTRO = 2\n", encoding="utf-8")
    # main.py importa SOLO el módulo usado.
    (proyecto / "main.py").write_text(
        "from proyecto.comun.usado import VALOR\nprint(VALOR)\n", encoding="utf-8"
    )
    return proyecto, comun


def test_detecta_modulo_huerfano(tmp_path):
    proyecto, comun = _crear_proyecto(tmp_path)
    huerfanos = modulos_huerfanos(comun, raiz_proyecto=tmp_path)
    nombres = {p.name for p in huerfanos}
    assert "huerfano.py" in nombres
    assert "usado.py" not in nombres


def test_init_no_se_marca(tmp_path):
    proyecto, comun = _crear_proyecto(tmp_path)
    huerfanos = modulos_huerfanos(comun, raiz_proyecto=tmp_path)
    assert all(p.name != "__init__.py" for p in huerfanos)


def test_import_from_package_cuenta_como_uso(tmp_path):
    proyecto, comun = _crear_proyecto(tmp_path)
    # Reescribir main para importar vía 'from ... import huerfano'
    (proyecto / "main.py").write_text(
        "from proyecto.comun import usado, huerfano\n", encoding="utf-8"
    )
    huerfanos = modulos_huerfanos(comun, raiz_proyecto=tmp_path)
    assert huerfanos == []
