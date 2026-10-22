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

| ID | Qué | Specs | Estado |
|---|---|---|---|
| T1 | Scaffold Vite + React + TS, tokens y base tipográfica | S5 | hecho |
| T2 | AppShell, Sidebar, TopBar, responsive con drawer | S2, S6 | hecho |
| T3 | Contexto de idioma activo persistente y badge de nivel | S3 | hecho |
| T4 | Pantalla de conversación: tarjetas, hilo, chips, acciones de mensaje | S1, S4 | hecho |
| T5 | Compositor con Enter/Shift+Enter y acciones deshabilitadas declaradas | S4, S7 | hecho |
| T6 | Vistas base de Lecciones, Planes, Traducción, Progreso, Idiomas, Configuración | S2, S7 | hecho |
| T7 | Estados vacío/carga/error, banner offline, manifest PWA | S8 | hecho |
| T8 | Verificación: build + typecheck, checklist §14 | S1–S8 | hecho |

## Log

**L1** — «quiero como esta en @desing.md» (resuelve Q1/Q2: manda el texto del documento sobre el wireframe).

**L2** — Framework elegido para arrancar F1: «React + Vite + TypeScript (recomendado)».

**L3** — Verificación T8: `npm run build` (tsc -b + vite build) sin errores; servidor de previsualización responde 200 en `/`.
