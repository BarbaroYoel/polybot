# F1 — Carcasa de la PWA con datos de ejemplo

Feature del roadmap F1 (`docs/roadmap.md`). Autorizada al confirmar React + Vite + TypeScript (ADR-010).
Rama: `feat/f1-pwa-shell`.

## Specs

**S1 — El chat es el centro.** `desing.md` §1: «Principio rector: el chat es el centro de la experiencia. Las otras funciones complementan las conversaciones, no las complican.» La pantalla inicial es la conversación, no un dashboard.

**S2 — Navegación completa.** `desing.md` §4: sidebar con «Conversaciones», «Lecciones», «Planes de estudio», «Traducción en tiempo real», «Progreso»; debajo «Mis idiomas» con acción `+`; «Configuración» fijada al pie. Medida: «Sidebar: 260–300px; puede contraerse a modo íconos u ocultarse.»

**S3 — Un idioma activo, visible.** `desing.md` §4: «Solo un idioma activo a la vez.» El wireframe muestra ejemplos «Inglés · B1», «Francés · A1», «Alemán · B2». El nivel se muestra como badge de solo lectura (ADR-008).

**S4 — Compositor.** `desing.md` §6.1: «Placeholder: «Escribe o habla…»» y «`Enter` envía; `Shift + Enter` inserta salto de línea.» Acciones: adjuntar, voz en vivo, micrófono, enviar. «Botones deshabilitados cuando la acción no corresponda.»

**S5 — Sistema visual.** `desing.md` §3: tokens `--bg-app #FFFFFF`, `--bg-sidebar #F5F5F5`, `--bg-surface #FAFAFA`, `--bg-hover #ECECEC`, `--bg-user-message #EDEDED`, `--text-primary #171717`, `--text-secondary #666666`, `--border-subtle #E5E5E5`, `--accent-neutral #555555`; radios 8/12/18/999px; escala de espacio «4 / 8 / 12 / 16 / 24 / 32px». Fuente Inter o sans-serif de sistema. Ancho de conversación «760–900px, centrado».

**S6 — Responsive.** `desing.md` §9: escritorio «≥ 1024px» con sidebar persistente; tablet 768–1023px con sidebar colapsable; móvil «< 768px» con sidebar como drawer.

**S7 — Honestidad del prototipo.** `desing.md` §6.1: «no usar controles decorativos que aparenten funcionar». §14: «Ningún botón visual implica una función inexistente sin indicar que es prototipo». §15: «Si todavía no existe backend, emplear datos de ejemplo claramente identificados».

**S8 — Estados y PWA.** `desing.md` §8: estados de primer uso, chat vacío, cargando, error de red, permiso denegado. §9: «Instalable en escritorio y móvil (manifest, íconos, metadatos adecuados)» y «Estado visible cuando no hay conexión».

## Tasks

| ID | Qué | Specs | Estado | Commit |
|---|---|---|---|---|
| T1 | Scaffold Vite + React + TS, tokens y base tipográfica | S5 | hecho | 6edf97f |
| T2 | AppShell, Sidebar, TopBar, responsive con drawer | S2, S6 | hecho | 6edf97f |
| T3 | Contexto de idioma activo persistente y badge de nivel | S3 | hecho | 6edf97f |
| T4 | Pantalla de conversación: tarjetas, hilo, chips, acciones de mensaje | S1, S4 | hecho | e9efeed |
| T5 | Compositor con Enter/Shift+Enter y acciones deshabilitadas declaradas | S4, S7 | hecho | e9efeed |
| T6 | Vistas base de Lecciones, Planes, Traducción, Progreso, Idiomas, Configuración | S2, S7 | hecho | 6edf97f |
| T7 | Estados vacío/carga/error, banner offline, manifest PWA | S8 | hecho | 6edf97f, e9efeed |
| T8 | Verificación: build + typecheck, checklist §14 | S1–S8 | hecho | — (ver L3) |

## Slices

| Slice | Commit | Líneas de autor | Contenido |
|---|---|---|---|
| 1 | f4abaab | ~50 | ADR-010, Q3 resuelto, este documento |
| 2 | 6edf97f | ~1000 | scaffold + shell + navegación + vistas base |
| 3 | e9efeed | ~550 | pantalla de conversación + compositor + wiring de rutas |
| 4 | — | ~40 | documentación de comandos y estado F1 |

**Sobre el tamaño.** El slice 2 supera la guía de ~400 líneas. Se aceptó a propósito: el shell, la navegación
y las vistas base comparten tokens, layout y contexto de idioma, así que partirlas produciría commits que no
compilan ni se pueden revisar solos. La unidad de revisión real de esta entrega es la rama `feat/f1-pwa-shell`
completa, que corresponde a un único entregable del roadmap (F1).

## Log

**L1** — «quiero como esta en @desing.md» (resuelve Q1/Q2: manda el texto del documento sobre el wireframe).

**L2** — Framework elegido para arrancar F1: «React + Vite + TypeScript (recomendado)».

**L3** — Verificación T8 (observada, no inferida):

- `npm run build` → `tsc --noEmit` sin errores + `vite build` en 560 ms, 57 módulos, bundle 183.93 kB (60.18 kB gzip).
- `npm run preview` → `GET /` 200, `GET /lessons` 200 (fallback SPA), `GET /manifest.webmanifest` 200; el HTML sirve `<title>Polybot — Tutor de idiomas</title>` y `<div id="root"></div>`.
- Cada uno de los tres commits de código se verificó con build verde antes de commitear.

**L4** — Slice 2 supera la guía de ~400 líneas y se documentó el motivo en `## Slices`; la unidad de revisión es la rama de F1.

## Verificación contra `desing.md` §14

| Criterio | Cómo se cumple |
|---|---|
| Simple, limpia, centrada en el chat | La ruta inicial es el hilo; las tarjetas son una fila, no un dashboard. |
| Sidebar con todas las secciones y Mis idiomas | `Sidebar.tsx`: 5 secciones + Mis idiomas + Configuración al pie. |
| Pantalla principal según el wireframe | Misma jerarquía: cabecera, 3 tarjetas, hilo, compositor. Valores de color según tokens (ADR-009). |
| Idioma activo y nivel evidentes | Chip en la TopBar + badge de nivel + resaltado en el sidebar. |
| Conversación nueva e historial | El historial de ejemplo se filtra por idioma activo; «Nueva conversación» está deshabilitado y lo declara. |
| Compositor con texto y voz identificados | Textarea + adjuntar/voz en vivo/micrófono/enviar, los tres de audio deshabilitados con motivo. |
| Traducción y repetición de audio claras | «Traducir» funciona localmente; «Escuchar» deshabilitado hasta F4. |
| Lecciones, planes, traducción y progreso consistentes | Mismo `SectionPage` para las cuatro. |
| Responsive escritorio y móvil | Grid de sidebar persistente ≥1024px; drawer con overlay <1024px; tarjetas 3→2→1 columnas. |
| Estados vacío, carga, error y permisos | `EmptyState` (idioma sin conversaciones), `LoadingState` (Suspense del chat), `ErrorState` (error boundary de rutas), banner offline. Permiso de micrófono queda para F4, cuando exista el micrófono. |
| Ningún botón implica función inexistente | Todos los controles sin backend están `disabled` con `title` que nombra la fase. |
| Frontend sin dependencia del harness | Solo `react`, `react-dom`, `react-router-dom`; ninguna referencia a Pi/OpenCode. |
