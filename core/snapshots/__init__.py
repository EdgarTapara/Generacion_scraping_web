"""Captura de snapshots HTML durante una corrida.

Cuando un portal cambia su frontend, el handoff entre el scraper que
falla y la persona/IA que lo repara depende de **tener el HTML que
vio el scraper en ese momento**. Sin snapshot, hay que reproducir la
condición a mano y casi nunca se logra (Cloudflare cambia, A/B tests
varían, etc.).

`guardar_snapshot_html` se llama desde cada portal_scraper en puntos
clave (listado cargado, detalle abierto, fallback DOM activado) y
registra el archivo en `diagnostico["snapshots_html"]` para que el
reporte de mantenimiento luego los liste.
"""

from core.snapshots.html import guardar_snapshot_html

__all__ = ["guardar_snapshot_html"]
