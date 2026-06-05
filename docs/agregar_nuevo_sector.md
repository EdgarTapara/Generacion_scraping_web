# Agregar un sector nuevo — checklist

Esta guía es para construir un scraper nuevo (empleo, financiero,
comercio, etc.) reutilizando `core/`. No es una receta para improvisar un
script rápido: es el checklist mínimo para que otro agente IA respete la
metodología BCRP ya validada.

El tiempo real depende de la fuente. Un portal simple puede llegar a primera
corrida en pocas horas; producción robusta exige fixtures, control de calidad,
historial, Excel consolidado y validación manual acotada.

## Paso 0 — Compuerta de intake (antes de codear)

Antes de cualquier código, completá la **compuerta de intake** de
`AGENTS.md` (es regla, no sugerencia):

1. **Entrevista de propósito**: ¿para qué se scrapea?, ¿qué universo?, ¿foto
   puntual o serie longitudinal? Sin esto no sabés si hace falta historial.
2. **Exposición de hallazgos**: inspeccioná la fuente y devolvele al usuario
   qué datos hay de verdad, si hay fecha de publicación (de ahí sale el
   periodo, nunca de la extracción), volumen/paginación, cada cuánto correr,
   y si basta `core.http` o exige `core.browser`. Que el usuario confirme.

## Antes de empezar

- [ ] Definir el **sector** en una palabra (`empleo`, `financiero`,
      `comercio`). Eso es lo que va en `config.SECTOR`.
- [ ] Definir si la fuente es web, API o documental/PDF. Si es documental,
      leer `docs/fuentes_documentales.md` antes de copiar el template web.
- [ ] Listar los **portales** objetivo y para cada uno: ¿tiene API pública /
      JSON / XHR? ¿HTML server-side? ¿es SPA Next.js (con `__NEXT_DATA__`)?
      ¿requiere login? La respuesta decide HTTP-first vs navegador (Paso 4).
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

**Primero decidí el transporte (HTTP-first).** No abras un navegador por
default — es el antipatrón más caro del proyecto. Orden:

1. ¿API / JSON / XHR? → `core.http.HttpClient` directo.
2. ¿HTML server-side? → `core.http` + parser (BeautifulSoup / JSON-LD).
3. ¿SPA Next.js? → muchas veces `core.redux.extraer_next_data(html)` ya trae
   el estado SIN navegador. Probalo antes de Selenium.
4. Sólo si nada de lo anterior alcanza, o `core.http.detectar_bloqueo_anti_bot`
   confirma un desafío → `core.browser.BrowserManager`.

En `portal_scrapers/<portal>.py` (NO `portales/` — convención v1):

- [ ] Función pública: `scrape_listados_<portal>(cliente_o_browser, operacion,
      num_paginas, diagnostico=None) -> list[dict]`. El diagnóstico se
      construye con `core.calidad.nuevo_diagnostico_scraping(...)` y se
      modifica in-place — el caller lo pasa.
- [ ] Si usás `core.http`, ante cada respuesta corré
      `detectar_bloqueo_anti_bot(r.status_code, r.text)` y, si dispara,
      guardá el motivo en `diagnostico["anti_bot"]` (el reporte lo escala).
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

- [ ] **Declará el transporte en el contrato.** Hacé que cada portal cumpla
      `core.contratos.PortalScraper`: atributos `fuente` y `cliente_preferido`
      (`"http"`/`"browser"`/`"hybrid"`) y métodos `descubrir_listado(operacion)
      -> list[RefAnuncio]` (barato) y `extraer_detalle(ref) -> AnuncioBase|None`
      (caro). Es tipado estructural: no hay que heredar nada. Separar
      descubrimiento de detalle permite pedir el detalle SÓLO de refs nuevas.
- [ ] Si el listado puede quedar **truncado** (tope de páginas con indicios de
      más resultados), registralo en `diagnostico["listado_completo"]=False`
      para que el historial no marque bajas falsas (Paso 8).

`scraper.py` queda como fachada delgada que sólo rutea al módulo del
portal según `portal`. No metas lógica de parsing en `scraper.py`.

Si dos portales del sector comparten arquitectura (ej. Navent =
Urbania + AdondeVivir), centralizar en `portal_scrapers/common.py`.

### Si la fuente es PDF/diario

No crear un falso portal Selenium. Usar:

- `core.ingesta.leer_pdf_columnas(...)` para reconstruir lectura por columnas.
- `core.ingesta.segmentar_documento(...)` para cortar avisos por codigo/seccion.
- Un parser por fuente (`diarios/<fuente>.py`, `boletines/<fuente>.py`, etc.).
- `id_fuente` en historial, por ejemplo `el_pueblo:2026-05-16`, para que un
  rerun de la misma edicion no infle apariciones ni marque bajas falsas.

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
- [ ] Derivar columnas de periodo desde la fecha de publicación:
      `agregar_columnas_periodo(df, "fecha_publicacion")`. Esto agrega
      `anio` (int), `trimestre` (`YYYY-T{1..4}`) y `mes` (`YYYY-MM`). El
      BCRP agrega por trimestre, así que estas columnas son obligatorias
      en cualquier sector con fecha. Viajan solas al Excel; para que
      lleguen a SQL hay que declararlas en `campos_snapshot` (Paso 8).
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
- [ ] Mejor aún: declarar `SUPERFICIE_POR_CATEGORIA` en `config.py` y pasarlo
      como `superficie_por_categoria=...`. El reporte clasifica el fallo
      (`RED_O_PORTAL_CAIDO` / `ANTI_BOT` / `FRONTEND_LISTADO` / `DETALLE` /
      `COBERTURA_BAJA`) y apunta a la superficie EXACTA por categoría, así la
      IA auditora no revisa todo. Ejemplo: `{"LISTADO": ["portal_scrapers/
      <portal>.py: scrape_listados"], "LIMPIEZA": ["limpieza.py"], "ANTI_BOT":
      ["usar core.browser para este portal"]}`.

## Paso 7 — Cache + IA

En `extractor_ia.py`:

- [ ] Confirmar si IA es necesaria. Si el campo se puede resolver con API
      oficial, regex confiable o tabla de referencia, no mandar al modelo.
- [ ] Definir `_SYSTEM_PROMPT` con reglas estrictas (qué NO devolver,
      longitud máxima, formato JSON). `temperature=0.0` para reproducibilidad.
- [ ] El campo a resolver por IA debe ser **uno** por extractor (si hay
      más, encadenar). Esto facilita auditar y reusar cache.
- [ ] Asignar `publicacion_id` con `core.utils.asignar_publicacion_id(df, sector)`.
- [ ] Aplicar cache antes de llamar al modelo:
      `cache.aplicar_a_dataframe(df, campo)`.
- [ ] Sólo enviar pendientes a DeepSeek. Guardar respuestas nuevas con
      `cache.guardar(...)` o `cache.guardar_dataframe(...)`.

DeepSeek es el adaptador por defecto del template, no una decisión de negocio.
Si el sector usa OpenAI, Anthropic, Gemini u otro proveedor, mantener el mismo
patrón: cache primero, IA solo para pendientes, salida validada antes de SQLite.

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
- [ ] Incluir las columnas de periodo para poder agregar en SQL por
      trimestre/mes: `("anio", "INTEGER"), ("trimestre", "TEXT"),
      ("mes", "TEXT")`. Sin esto, `SELECT trimestre, AVG(precio) ...
      GROUP BY trimestre` no es posible directo desde SQLite.
- [ ] Si el sector NO tiene operaciones, pasar `campo_operacion=None`
      y `operacion=None`.
- [ ] Si la fuente tiene identidad propia de edicion/lote/PDF, pasar
      `id_fuente=<fuente>:<fecha_o_hash>` y no usar `permitir_rerun=True`
      salvo reproceso manual validado.
- [ ] Una corrida degradada no debe mutar ausencias/bajas. El default de
      `HistorialSQLite` ya protege este caso; si se fuerza, documentar por que.
- [ ] **El alcance del ciclo de vida es el eje de consulta.** `campo_operacion`
      debe ser lo que pediste en la corrida (región/operación), no un campo
      declarado dentro del aviso. Si "región consultada" ≠ "región observada",
      usá la consultada como `operacion` y guardá la observada como dato.
- [ ] **Listado parcial → `listado_completo=False`.** Si el listado quedó
      truncado, pasalo a `registrar_corrida(...)`: no marcará ausencias. Para
      portales siempre parciales, configurá `dias_vejez=N` en el constructor
      para retirar lo no visto en > N días. La guarda anti-colapso
      (`fraccion_colapso`/`min_base_colapso`) ya viene activa por defecto.

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
