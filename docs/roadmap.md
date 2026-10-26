# Roadmap — Polybot

Cada fase termina con algo verificable por un humano. Estado actual: **F5 (lecciones y planes)
completada** en su rama (`8ba8964`, `00d8dcb`), entregada como cadena de PRs sobre esa rama. F6 y F7
pendientes.

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

## F3 — Chat de texto real — **completada** (rama `feat/f3-real-text-chat`)

Alcance, decisiones y evidencia: `odd/tasks/f3-real-text-chat.md`.

- [x] Puerto `LLM` + primer adaptador (una instancia de Pi por turno, ADR-013); prompt del tutor versionado (`tutor.v1`).
- [x] Streaming SSE del turno, con cancelación real y estado `error` persistido.
- [x] Correcciones y vocabulario sugerido al cerrar el turno, persistidos por idioma y devueltos en el detalle.
- [x] La PWA conversa de verdad: tokens en vivo, «Pensando…», «Detener», tarjetas de corrección y vocabulario.

**Verificación:** `uv run pytest` (102 passed), `ruff format`/`ruff check` limpios, `npm run typecheck` y
`npm run build` verdes, y turnos reales contra Pi en francés y en inglés: tokens, `message_end`, `correction` y
`vocabulary`, con el feedback persistido y sin mezclar datos entre idiomas. Detalle y límites conocidos (arranque
lento intermitente del proveedor, 60 s de presupuesto) en el documento de la fase.

## F3.5 — Traducción de mensajes y fragmentos — **completada**

Alcance, decisiones y evidencia: `odd/tasks/message-translation.md`. Decisión registrada: ADR-014.

- [x] «Traducir» en un mensaje del tutor: traduce el mensaje completo, persistido, y sobrevive a la recarga.
- [x] Con texto seleccionado dentro de la burbuja, traduce **solo esa selección**, sin guardarla, y cita el fragmento.
- [x] `POST /translate` (fragmento, sin estado) y `POST /conversations/{id}/messages/{message_id}/translation`
      (mensaje, persistido e idempotente), documentados en `docs/api-contract.md`.
- [x] La dirección sale del perfil del idioma de la conversación, nunca del idioma activo global.

**Verificación:** `uv run pytest` (123 passed), `ruff format --check`/`ruff check` limpios, `npm run typecheck` y
`npm run build` verdes, más la traducción real contra el Pi local. Detalle en el documento de la feature.

## F4 — Voz — **completada** (rama `feat/f3-real-text-chat`, sin commit propio)

Alcance, decisiones y evidencia: `odd/tasks/f4-voice.md`. Decisiones registradas: ADR-015 y ADR-016.

- [x] STT con **Whistle** (ADR-015): local por CPU, siete idiomas, vía `cactus-needle`; `POST /voice/transcribe`.
- [x] TTS con **Piper por binario** y caché por contenido (ADR-016); «Escuchar» y «Más lento» en el chat.
- [x] Estados visibles: escuchando, transcribiendo, pensando, reproduciendo. Texto transcripto editable antes de enviar.
- [ ] **Pendiente explícito, no silencioso:** streaming de voz por frases (hoy un clip por mensaje) y
      warm-up del motor al arrancar (el primer turno de un proceso paga ~2,6 s de carga del STT).

**Verificación:** `uv run pytest` (177 passed), `ruff format --check` y `ruff check` limpios,
`npm run typecheck` y `npm run build` verdes, y un turno de voz completo medido contra la API real:
transcribir 2,81 s en frío / 0,19 s en caliente, turno del tutor 11,31 s con primer token a 4,23 s,
síntesis 0,32 s y caché en 0,00 s. La voz nunca reemplaza al texto: el transcripto se edita en el compositor.
Detalle en `odd/tasks/f4-voice.md` L7.

## F5 — Lecciones y planes de estudio — **completada** (rama `feat/f5-lessons-plans`: `8ba8964`, `00d8dcb`)

Alcance, specs y evidencia: `odd/tasks/f5-lessons-plans.md`. Decisión registrada: ADR-017.

- [x] Catálogo por idioma con la lección siguiente destacada y el estado de cada lección derivado de los intentos (`0ca0673`).
- [x] Lección con ejercicios, corrección determinista, resultado con errores y vocabulario nuevo, y comentario del tutor best-effort (`0ca0673`).
- [x] Plan a partir de un objetivo, con cronograma por semanas, sesiones con estado derivado de los intentos y ajuste explícito del usuario (`bf2dca7`).
- [x] PWA: catálogo, vista de lección y pantalla de plan.

**Verificación T4:** `npm run typecheck` y `npm run build` verdes; `uv run pytest` 201 passed.
El agente reportó catálogo, intentos y planes reales, aislamiento por idioma y ausencia de overflow
a 375×812 y 1280×900; el orquestador repitió typecheck con exit 0.

**Verificación T5:** `uv run pytest` **203 passed**, `uv run ruff check` y `ruff format --check`
limpios, `npm run typecheck` y `npm run build` verdes. Una verificación independiente, sobre una
copia aislada y su propia base migrada y sembrada, confirmó los tres puntos pedidos:

1. Con `PI_BIN_PATH` apuntando a un binario inexistente, `POST /lessons/{id}/submit` devuelve 200
   con 3/3, el intento persistido, `feedback: null` y el catálogo del idioma avanzado; en francés
   todo sigue `pending`. El chat responde `llm_unavailable` por SSE y la traducción 502
   `llm_unavailable`, sin 500.
2. Las listas de lecciones, ejercicios, semanas y sesiones muestran una sola numeración, con
   `list-style: none` y sin marcador nativo, a 375×812 y 1280×900, sin desborde horizontal.
3. El adaptador de Pi conserva flags de aislamiento, presupuesto de tiempo, directorio temporal y
   cancelación; las suites de chat, cierre de turno y traducción siguen en verde.

**Límites conocidos:** dos planes del mismo idioma creados en carrera pueden responder 500 en vez
de 409 (v0 de un solo usuario, anotado en `odd/tasks/f5-lessons-plans.md` L4); el frontend no tiene
suite de tests porque el stack de testing sigue sin decidirse (`docs/stack.md`); el slice de la PWA
suma 2.466 líneas y no se puede partir sin romper el build, así que se entrega como cadena de PRs
sobre la rama.

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
