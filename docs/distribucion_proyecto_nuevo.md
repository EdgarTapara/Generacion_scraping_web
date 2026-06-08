# Distribución: cómo consume la metodología un proyecto nuevo

> Para agentes IA que construyen un scraper en **otra carpeta/repo** (no
> como sector dentro de `bcrp-scraping`). El caso real es el scraper de
> empleo, que vive aparte y no puede `import core`.

## El problema que esto resuelve

Cuando un proyecto standalone adopta la metodología, la tentación es copiar
`core/` entero a un paquete local (`comun/`). Eso deja **archivos muertos**:
módulos que el proyecto nunca importa pero que ensucian el árbol y confunden
a quien lo revisa archivo por archivo ("¿por qué hay un `modelos.py` que
nadie usa?"). Pasó en empleo (`comun/modelos` se borró por 0 importadores).

La desincronización entre el framework y el proyecto es **por diseño** (se
actualiza a mano). Pero "desincronizado" no debe significar "lleno de basura".

## Regla: generación selectiva + manifiesto + poda

### 1. Generá sólo lo que el proyecto importa

No copies `core/` completo "por si acaso". Mirá qué necesita el proyecto y
traé sólo eso a su paquete compartido (`<proyecto>/comun/`):

| El proyecto hace… | Trae a `comun/` |
|---|---|
| HTTP a portales server-side / API | `http` (cliente + anti_bot), `utils` |
| Limpieza de campos | `limpieza` (sólo los helpers que usa) |
| Serie longitudinal | `historial`, `calidad` |
| Salida Excel | `reportes` |
| Campos no estructurados con IA | `extractor_ia` (cache + adaptador) |
| Mantenimiento ante cambios | `mantenimiento_frontend`, `snapshots` |

Si el proyecto no usa navegador, **no copies `core/browser`**. Si no usa NSE
ni tipo de cambio, no los traigas. Cada módulo presente debe tener al menos
un importador real.

### 2. Anotá la procedencia (manifiesto)

Creá `comun/PROCEDENCIA.md` con una fila por módulo adoptado:

```markdown
| módulo            | origen en bcrp-scraping        | fecha     | adaptaciones |
|-------------------|--------------------------------|-----------|--------------|
| comun/http        | core/http                      | 2026-06-03| ninguna      |
| comun/historial   | core/historial                 | 2026-06-03| +id_fuente   |
| comun/calidad     | core/calidad                   | 2026-06-03| umbrales empleo |
```

Esto hace **visible** qué se copió, de dónde y qué se tocó — así re-sincronizar
un módulo puntual no es adivinanza. Si un módulo diverge mucho, la fila lo
declara.

### 3. Corré la compuerta de poda antes de cerrar

```bash
python -m core.poda <proyecto>/comun
```

Lista los módulos del paquete con **0 importadores**. Revisá cada uno: si de
verdad nadie lo usa, **borralo**. La herramienta sale con código 1 si hay
huérfanos, así sirve como gate (CI o checklist de cierre). No cierres una
tarea con código muerto adentro.

## Alternativa descartada (por ahora): paquete instalable

Se evaluó volver `bcrp-scraping` instalable (`pip install -e`) para que los
proyectos hicieran `from bcrp_scraping.core import ...` sin copiar. Es la
opción más limpia a futuro (una sola fuente de verdad), pero hoy:

- Acopla cada proyecto al path/repo del framework.
- Exige empaquetado (`pyproject.toml`) y versionado.
- Complica correr un proyecto en una máquina sin el framework al lado.

Decisión vigente: **generación selectiva + poda**. Si en el futuro hay 3+
proyectos consumiendo `core/`, reconsiderar el paquete instalable.

## Checklist de cierre para un proyecto standalone

- [ ] Cada módulo de `comun/` tiene al menos un importador real.
- [ ] `comun/PROCEDENCIA.md` existe y está al día.
- [ ] `python -m core.poda <proyecto>/comun` sale limpio.
- [ ] No se copió `core/browser` si el proyecto no usa navegador (HTTP-first).
- [ ] Los tests del proyecto corren sin red ni Chrome.
