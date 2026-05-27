"""Scrapers por portal del sector <SECTOR>.

Cada portal vive en su propio archivo (`navent.py`, `properati.py`, ...)
para que un cambio en un portal NO toque la lógica de los demás.

`common.py` agrupa lo compartido entre portales del mismo sector
(helpers de tarjeta, normalizaciones de campo, decisiones de retry).
NO meter lógica genérica acá si ya existe en `core/` — usar core.
"""
