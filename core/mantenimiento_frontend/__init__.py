"""Mantenimiento dinámico ante cambios de frontend en portales.

Cuando un portal cambia su HTML, JSON embebido o impone anti-bot
nuevo, la corrida queda `sin_datos`, `degradado` o lanza una excepción.
El framework no intenta auto-reparar — eso es prácticamente imposible
sin contexto humano. Lo que sí hace es **dejar un paquete auditable**
para que una persona o IA técnica entienda qué se rompió y lo arregle:

* Snapshot HTML de la página problemática (ver `core.snapshots`).
* Diagnóstico estructurado (ver `core.calidad.diagnostico`).
* **Reporte Markdown** generado por este módulo, que une los anteriores
  con instrucciones específicas y un mapa portal → archivos donde
  buscar la causa.

El sector declara su propio `_codigo_por_portal` para que el reporte
apunte a sus archivos (no hay un mapa hardcodeado en `core/`).
"""

from core.mantenimiento_frontend.reporte import (
    clasificar_fallo,
    generar_reporte_mantenimiento_frontend,
)

__all__ = ["clasificar_fallo", "generar_reporte_mantenimiento_frontend"]
