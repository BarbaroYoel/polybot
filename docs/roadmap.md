# Roadmap — Polybot

Cada fase termina con algo verificable por un humano. Estado actual: **F2**.

## F0 — Base documental

- [x] `desing.md` con producto, pantallas, estados y criterios de aceptación.
- [x] Contrato de trabajo para agentes (`AGENTS.md`).
- [x] Arquitectura, stack, contrato de API, convenciones y decisiones.
- [x] Repositorio Git inicializado y primer commit (`4c27b58`).
- [ ] Repositorio remoto y política de ramas.

**Salida:** cualquier agente puede leer el repo y saber qué construir sin inventar decisiones.

## F1 — Carcasa de la PWA con datos de ejemplo — **completada** (rama `feat/f1-pwa-shell`)

Alcance: `desing.md` §13, puntos 1–5. Detalle y evidencia: `odd/tasks/f1-pwa-shell.md`.

- [x] Shell con sidebar, cabecera y navegación (todas las secciones).
- [x] Inicio con las tarjetas de resumen y el historial del idioma activo, separado de la conversación (`/` y `/chat/:conversationId`, ADR-011).
- [x] Pantalla de conversación completa: mensajes, sugerencias rápidas, compositor.
- [x] Selector de idioma con contexto persistente entre recargas.
- [x] Vistas base de Lecciones, Planes, Traducción y Progreso con datos de ejemplo identificados.
- [x] Estados vacíos, de carga, de error y de permiso; banner sin conexión.
- [x] Responsive escritorio / tablet / móvil.
- [x] Build y typecheck verdes; verificación de checklist §14 registrada en el documento de la feature.

**Verificación:** checklist de `desing.md` §14 completa (tabla en `odd/tasks/f1-pwa-shell.md` §Verificación).
La separación inicio / conversación se verificó con una sonda de geometría en Chrome headless sobre ocho viewports
(`odd/tasks/chat-home-split.md`).
El permiso de micrófono queda explícitamente para F4, cuando exista el micrófono.

## F2 — Esqueleto del backend y contrato real — **completada** (rama `feat/f2-backend-skeleton`)

Alcance, decisiones y evidencia: `odd/tasks/f2-backend-skeleton.md`.

- [x] FastAPI con `/health`, configuración tipada (`pydantic-settings`) y sobre de error uniforme para todo error, incluidos los 422 de validación.
- [x] `/languages` con persistencia: listar, agregar, cambiar nivel/meta/activo (uno activo a la vez) y archivar de forma blanda.
- [x] `/conversations` con persistencia: historial del idioma con cursor, crear, detalle con mensajes paginados, renombrar y eliminar.
- [x] Esquema y migración inicial con SQLAlchemy 2 + Alembic sobre SQLite, más seed idempotente con los datos de ejemplo.
- [x] Suite de tests del backend sobre una base migrada por Alembic.
- [x] La PWA de F1 consume datos reales en esas dos secciones; con el backend caído muestra un estado de error, no un historial inventado.

**Verificación:** `uv run pytest` (37 passed), `uv run ruff format --check` y `uv run ruff check` limpios, `npm run typecheck`
y `npm run build` verdes, y una sonda con Chrome headless contra la API real que comprueba inicio, `/languages`,
`/chat/:id`, el cambio de contexto al abrir una conversación de otro idioma, el 404 de una conversación inexistente
y el estado de error con el backend caído. Detalle en `odd/tasks/f2-backend-skeleton.md` §Verificación.

## F3 — Chat de texto real

- Puerto `LLM` + primer adaptador; prompt del tutor versionado.
- Streaming SSE del turno, con cancelación.
- Correcciones y vocabulario sugerido al cerrar el turno.

**Verificación:** conversación real por texto, con historial y cambio de idioma sin mezclar datos.

## F4 — Voz

- STT (decidir el modelo: ver `docs/stack.md`).
- TTS con Piper, streaming por frases y caché.
- Estados visibles: escuchando, transcribiendo, pensando, reproduciendo. Edición del texto transcripto antes de enviar.

**Verificación:** turno de voz completo con latencia medida y aceptable; texto siempre visible como alternativa.

## F5 — Lecciones y planes de estudio

- Catálogo, lección con ejercicios, feedback y cierre.
- Creación de plan a partir de un objetivo; sesiones con estado.

**Verificación:** completar una lección y ver el progreso reflejado.

## F6 — Progreso

- Resumen, evolución por destreza, errores frecuentes, historial.
- Nivel como dato trazable, no como medición infalible.

**Verificación:** el progreso refleja las sesiones reales de F3–F5.

## F7 — Intérprete en tiempo real

- WebSocket, segmentos continuos, transcripción + traducción por turno.
- Aviso visible de latencia y precisión variables.

**Verificación:** conversación de prueba con dos idiomas y fragmentos ordenados temporalmente.

## Fuera de alcance

Pagos, gamificación extensa, redes sociales, marketplace, personajes 3D, analíticas complejas, identidad de marca definitiva
(`desing.md` §13).
