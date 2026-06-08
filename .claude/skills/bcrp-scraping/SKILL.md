---
name: bcrp-scraping
description: Usar para CUALQUIER tarea de web scraping o ingesta de datos del BCRP — construir un scraper nuevo, arreglar uno existente, parsear portales (Selenium, Playwright, requests, BeautifulSoup, APIs/JSON/XHR, SPA/Next.js, anti-bot), extraer tablas/datos de PDFs o diarios, historial SQLite, salidas Excel, extracción con IA/DeepSeek, compuertas de calidad, o auditar/reparar scrapers. Esta metodología (core/ + AGENTS.md) es el punto de partida obligatorio antes de escribir código. Sirve para cualquier agente (Claude Code, Codex, Antigravity, Gemini).
---

# bcrp-scraping — punto de partida del scraping BCRP

## Regla dura

Ante **cualquier** pedido de scraping o ingesta de datos para el BCRP, lo
PRIMERO es leer el contrato de este proyecto antes de escribir una línea:

1. **`AGENTS.md`** (raíz de este repo) — filosofía, capas, reglas que no se
   rompen, compuerta de intake, HTTP-first, mantenimiento ante cambios de
   frontend. Es el contrato.
2. **`core/`** — los patrones ya resueltos. No reinventar uno que ya existe.
3. **`README.md`** y **`guia.html`** para el panorama; **`docs/`** para el
   detalle (estructura, distribución, fuentes documentales/PDF, runbook).

No se arranca un scraper desde cero ni se copia lógica entre proyectos sin
preguntar antes "¿esto debería vivir en `core/`?".

## Qué es este proyecto

Metodología pura de scraping reutilizable: `core/` (patrones sector-agnósticos)
+ `plantilla_proyecto/` (la estructura ESTÁNDAR de un scraper nuevo). **No
contiene scrapers de producción.** Cada scraper real vive en su propia
carpeta/repo, copia la plantilla y trae de `core/` sólo lo que importa.

## Flujo al recibir un pedido de scraping

1. **Compuerta de intake** (AGENTS.md): confirmá propósito (¿para qué pregunta
   económica?), universo (región/segmento), y horizonte (foto vs. serie
   longitudinal) ANTES de tocar el sitio. Luego inspeccioná la fuente y exponé
   qué datos hay *realmente* antes de construir.
2. **HTTP-first**: API/JSON/XHR → HTML server-side → `__NEXT_DATA__` con
   `core.redux` (sin navegador) → y sólo si nada alcanza, `core.browser`.
3. **Construir** copiando `plantilla_proyecto/` (imports relativos: renombrar
   no rompe nada) y reutilizando `core/`. Seguir `docs/agregar_nuevo_sector.md`.
4. **No romper** las reglas duras: calidad antes de IA, `normalizar_enlace`
   único, lectura en cascada, listado parcial no marca bajas, similitud nunca
   borra sola, TC no sobrescribe lo observado, IA es adaptador no metodología.
5. **Validar** con tests sin red ni Chrome (fixtures locales). No presentar un
   smoke test como validación completa.

## Para proyectos standalone (fuera de este repo)

No copiar `core/` entero: traer sólo los módulos que el proyecto importa,
anotar procedencia y correr la poda — `python -m core.poda <paquete>` — para no
dejar código muerto. Ver `docs/distribucion_proyecto_nuevo.md`.

## La verdad está en los archivos

Memoria, resúmenes viejos y espejos de GitHub pueden estar desactualizados.
Antes de afirmar o editar, inspeccioná los archivos vigentes del proyecto.
