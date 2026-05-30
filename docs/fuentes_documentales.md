# Fuentes documentales y diarios impresos

Esta guia captura lo aprendido en `INMOBILIARIA/v1-diarios` para fuentes que
no son portales web puros: PDFs, diarios impresos recortados, boletines y
clasificados escaneados o maquetados.

## Principio

No trates un PDF como si fuera HTML. Primero hay que reconstruir el orden de
lectura y dejar trazabilidad del documento fuente. Recien despues se aplican
regex, calidad, historial y Excel.

Flujo recomendado:

1. Ingesta documental.
2. Segmentacion por codigo/seccion.
3. Parser deterministico por fuente.
4. `publicacion_id` + `descripcion_hash`.
5. Compuerta de calidad.
6. IA fallback solo para avisos pobres en campos clave.
7. Historial SQLite idempotente por `id_fuente`.
8. Consolidado reconstruible desde SQLite.

## PDF por columnas

Para clasificados impresos, usar `core.ingesta.leer_pdf_columnas`.

La regla validada fue ordenar bloques de PyMuPDF por:

```text
round(x0 / ancho_columna), y0
```

Esto preserva columnas mejor que una extraccion lineal. La dependencia
`pymupdf` es opcional; instalar con el extra `pdf` o con `pip install pymupdf`.

## Segmentacion

Usar `core.ingesta.segmentar_documento` cuando cada aviso termina con un codigo
estable. El sector debe declarar:

- `codigo_regex`: captura el codigo completo del aviso.
- `seccion_regex`: captura la seccion dentro del codigo, si existe.
- `secciones_objetivo`: filtra secciones utiles antes de parsear.

Ejemplo de `v1-diarios`: procesar solo `S2`, `S3`, `E2`, `E3` y descartar
empleos, vehiculos, servicios u otras secciones antes del parser inmobiliario.

## Parser deterministico

Cada diario o boletin debe tener su propio modulo de parser. Los regex
compartidos viven en un `common.py` del sector; los detalles de layout quedan
en `diarios/<fuente>.py` o equivalente.

Buenas reglas:

- Desfragmentar texto justificado antes de buscar campos.
- Separar operacion, tipo, ubicacion, telefono y precio con regex explicitos.
- Usar diccionarios de alias para zonas abreviadas.
- Contar campos clave para decidir si entra IA fallback.
- Generar warnings de negocio, no excepciones, ante valores raros.

## Precio publicado

En clasificados PDF no uses un parser laxo de numeros pelados. Los telefonos
pueden venir pegados al monto:

```text
$680,000959553859
S/.900.00958225667
```

Usar `core.limpieza.extraer_precio_publicado_pe` para aceptar solo precios con
senal monetaria explicita y recortar telefonos pegados. Si no hay precio
publicado, dejar `precio=None` y representar `-` solo en Excel.

## Historial idempotente

Para PDFs o ediciones periodicas, pasar `id_fuente` a
`HistorialSQLite.registrar_corrida`, por ejemplo:

```python
historial.registrar_corrida(
    df,
    portal="el_pueblo",
    id_fuente="el_pueblo:2026-05-16",
)
```

Reglas:

- Reprocesar la misma fuente sin `permitir_rerun=True` no debe mutar SQLite.
- Un `permitir_rerun=True` refresca campos, pero no debe marcar ausencias de
  otros registros de la misma fuente.
- Una corrida degradada no debe incrementar ausencias ni dar bajas por defecto.
- Si se fuerza una degradada, debe haber validacion manual previa.

## Consolidado

Para fuentes documentales periodicas, preferir un consolidado reconstruido desde
SQLite antes que crear un Excel por fecha. SQLite es la fuente de verdad; Excel
es la vista analitica.

No se necesita una hoja separada de bajas si existe columna `estado_vigencia`.
Mantener activos y bajas juntos evita fragmentar el analisis longitudinal.

## Validacion

No basta con que el parser corra. Validar:

- Tests unitarios de segmentacion.
- Tests de precios con telefono pegado.
- Tests de rerun/idempotencia.
- Tests de corrida degradada sin mutar bajas.
- Rebuild del Excel desde SQLite.
- Reprocesamiento de una misma fuente con y sin `permitir_rerun`.
