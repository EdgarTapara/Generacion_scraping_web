# Agregar un sector nuevo — checklist

Esta guía es para construir un scraper nuevo (empleo, financiero,
comercio, etc.) reutilizando `core/`. Si todo va bien deberías llegar a
una primera corrida en 1-2 horas para un portal sencillo, y a una
producción robusta en 1-2 días con 3-4 portales.

## Antes de empezar

- [ ] Definir el **sector** en una palabra (`empleo`, `financiero`,
      `comercio`). Eso es lo que va en `config.SECTOR`.
- [ ] Listar los **portales** objetivo y para cada uno: ¿es SPA Next.js?
      ¿HTML server-side? ¿tiene API pública? ¿requiere login?
- [ ] Identificar las **operaciones** internas (alquiler/venta, full-time/
      part-time, etc.) o decidir que el sector no las usa.
- [ ] Conseguir credenciales / API keys necesarias y agregarlas a
      `.env.example`.

## Paso 1 — Scaffold

```bash
cp -r sectores/_template sectores/<mi_sector>
```

Y en el directorio nuevo:

- [ ] Reemplazar `<MI_SECTOR>` por el nombre real en `config.py`.
- [ ] Renombrar `AnuncioMiSector` en `modelos.py`.
- [ ] Reemplazar `from sectores._template import config` en `main.py`
      por `from sectores.<mi_sector> import config`.

## Paso 2 — Configuración

En `config.py`:

- [ ] `PORTALES_SOPORTADOS` con los nombres de los portales.
- [ ] `OPERACIONES` (lista o vacío si no aplica).
- [ ] `URLS` con plantillas parametrizadas por `{pagina}`. Si el portal
      tiene una URL distinta para la página 1, usar dict con keys
      `pagina_1` y `pagina_n` (como Properati en v1).
- [ ] `generar_url_listado(portal, operacion, pagina)` armado.
- [ ] Variables `.env`: API keys, overrides de Chrome.

## Paso 3 — Modelo Pydantic

En `modelos.py`:

- [ ] Heredar `AnuncioBase` y añadir SOLO los campos específicos del
      sector. No redefinir `enlace`, `portal`, `sector`, etc.
- [ ] Anotar tipos con `Optional[T]` y usar `Field(...)` para constraints
      (rangos, regex).
- [ ] Implementar `validar_anuncio(anuncio) -> list[str]` con reglas de
      negocio (rangos, taxonomías, consistencia entre campos).

## Paso 4 — Portales

En `portal_scrapers/<portal>.py` (NO `portales/` — convención v1):

- [ ] Función pública: `scrape_listados_<portal>(browser, operacion,
      num_paginas, diagnostico=None) -> list[dict]`. El diagnóstico se
      construye con `core.calidad.nuevo_diagnostico_scraping(...)` y se
      modifica in-place — el caller lo pasa.
- [ ] Patrón **Redux → DOM → regex → None** en cascada. Si el portal es
      Next.js, primero `core.redux.extraer_next_data(html)` +
      `core.redux.buscar_clave_recursivo(blob, "<clave>")`.
- [ ] Selectores DOM estables (data-test / data-qa / id). Evitar
      clases CSS que cambian con cada release.
- [ ] **En cada página visitada** llamar
      `core.snapshots.guardar_snapshot_html(driver, portal, op, pagina,
      etapa, config.CARPETA_SNAPSHOTS_FRONTEND, diagnostico)`. Sin
      esto, las corridas que fallan no dejan evidencia y la IA auditora
      no puede reparar el portal.
- [ ] Actualizar contadores: `paginas_visitadas`, `paginas_con_tarjetas`,
      `tarjetas_totales`, `redux_paginas_ok` / `redux_paginas_fallidas`.

`scraper.py` queda como fachada delgada que sólo rutea al módulo del
portal según `portal`. No metas lógica de parsing en `scraper.py`.

Si dos portales del sector comparten arquitectura (ej. Navent =
Urbania + AdondeVivir), centralizar en `portal_scrapers/common.py`.

## Paso 5 — Limpieza

En `limpieza.py`:

- [ ] `pipeline_limpieza(datos_crudos, portal, operacion)` que devuelva
      DataFrame.
- [ ] Para cada campo, fallback en cascada: prioridad Redux > DOM > regex.
- [ ] Usar `core.limpieza`:
      - `parsear_numero`, `parsear_entero` para texto a número.
      - `moneda_a_iso` para normalizar monedas peruanas.
      - `limpiar_precio_pe` para precios con primario + secundario.
      - `limpiar_fecha_relativa` para fechas en español.
- [ ] Agregar `fecha_extraccion` y `portal` a cada fila.
- [ ] Antes de devolver, validar con Pydantic y poner warnings en columna.

## Paso 6 — Compuerta de calidad

- [ ] Declarar `UMBRALES_CALIDAD` en `config.py` por (portal o estrategia, campo).
- [ ] En `main.py`, después de `pipeline_limpieza`, llamar
      `evaluar_cobertura(df, umbrales, señales_instrumentales)`.
- [ ] Si el `Veredicto.estado` es `DEGRADADO`, exportar a
      `resultados/degradadas/` y NO continuar con IA ni historial.
- [ ] En el MISMO punto, llamar
      `core.mantenimiento_frontend.generar_reporte_mantenimiento_frontend(...)`
      con el `diagnostico` (que incluye snapshots) y el `df`. Esto deja
      el handoff para la IA auditora.
- [ ] Declarar `CODIGO_POR_PORTAL` en `config.py` apuntando a las
      funciones reales de tus `portal_scrapers/<portal>.py`. El reporte
      lo usa para guiar la reparación.

## Paso 7 — Cache + IA

En `extractor_ia.py`:

- [ ] Definir `_SYSTEM_PROMPT` con reglas estrictas (qué NO devolver,
      longitud máxima, formato JSON). `temperature=0.0` para reproducibilidad.
- [ ] El campo a resolver por IA debe ser **uno** por extractor (si hay
      más, encadenar). Esto facilita auditar y reusar cache.
- [ ] Asignar `publicacion_id` con `core.utils.asignar_publicacion_id(df, sector)`.
- [ ] Aplicar cache antes de llamar al modelo:
      `cache.aplicar_a_dataframe(df, campo)`.
- [ ] Sólo enviar pendientes a DeepSeek. Guardar respuestas nuevas con
      `cache.guardar(...)` o `cache.guardar_dataframe(...)`.

## Paso 8 — Historial SQLite

En `main.py`:

```python
historial = HistorialSQLite(
    ruta_db=config.RUTA_DB,
    sector=config.SECTOR,
    campos_snapshot=[
        ("titulo", "TEXT"),
        ("precio", "REAL"),
        ("moneda", "TEXT"),
        # ... TODOS los campos que quieras auditar a lo largo del tiempo
    ],
    umbral_ausencias=config.UMBRAL_AUSENCIAS,
    campo_operacion="tipo_operacion" if config.OPERACIONES else None,
)
df, stats = historial.registrar_corrida(df, portal, operacion,
                                        estado_calidad=veredicto.estado.value)
```

- [ ] `campos_snapshot` debe incluir TODOS los campos cuya evolución te
      interese ver (cambio de precio, cambio de NSE, etc.).
- [ ] Si el sector NO tiene operaciones, pasar `campo_operacion=None`
      y `operacion=None`.

## Paso 9 — Exportar a Excel

```python
exporter = ExcelAcumulativo(
    ruta_archivo=str(config.CARPETA_SALIDA / config.NOMBRE_ARCHIVO_CONSOLIDADO),
    hojas=[
        Hoja("Consolidado", claves_dedup=["enlace"]),       # vista actual
        Hoja("Diagnostico", claves_dedup=["enlace", "fecha_extraccion"]),  # bitácora
    ],
)
exporter.escribir({
    "Consolidado": df_consolidado,
    "Diagnostico": df_diag,
})

# Opcional: pulir el Excel
aplicar_formato_hojas(
    exporter.ruta_archivo,
    hojas=["Consolidado", "Diagnostico"],
    anchos_columna={"titulo": 35, "enlace": 55, ...},
)
```

- [ ] Si el sector usa tipo de cambio, llamar después
      `aplicar_conversion_tipo_cambio(df, ruta_cache=config.RUTA_DB, modo=...)`
      y luego `marcar_columnas_estimadas_excel(...)` para pintar las
      celdas estimadas en rojo.

## Paso 10 — Tests

En `tests/sectores/<mi_sector>/`:

- [ ] Fixtures HTML grabadas en `tests/fixtures/<portal>/` (sin red).
- [ ] Tests del parser de cada portal usando esas fixtures.
- [ ] Test del pipeline de limpieza con un caso por portal.
- [ ] Test de roundtrip historial: insertar + repetir + ausentar.
- [ ] Test de export Excel con tmp_path.

## Verificación final

```bash
# Test
python -m pytest tests/sectores/<mi_sector>/ -v

# Corrida real, con pocas páginas y sin IA primero
python -m sectores.<mi_sector>.main --portal <portal_a> --paginas 1 --sin-ia

# Si pasa: agregar IA
python -m sectores.<mi_sector>.main --portal <portal_a> --paginas 1

# Si pasa: todos los portales
python -m sectores.<mi_sector>.main --paginas 5
```

## Cuándo subir algo a `core/`

Cuando estés implementando el **segundo** sector y notes que un patrón se
repite (`parsear_features_tarjeta`, `extraer_X_descripcion`, etc.),
levanta una propuesta para mover ese helper a `core/`. La regla es:

> Aparece en ≥ 2 sectores Y es sector-agnóstico (acepta nombres por
> parámetro) Y tiene tests sin red.

Si cumple los 3 criterios, va a `core/`. Si no, queda en el sector.
