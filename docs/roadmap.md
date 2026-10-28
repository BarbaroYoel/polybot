# Roadmap — Polybot

Cada fase termina con algo verificable por un humano. Estado actual: **F1–F7 completas**; F6.6 y F7
están mergeadas o listas para mergear desde sus ramas. El detalle y la evidencia viven en
`odd/tasks/`.

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

## F6 — Progreso — **completada** (rama `feat/f6-progress`)

Alcance, contrato y límites: `odd/tasks/f6-progress.md`. Decisión registrada: ADR-018.

- [x] `GET /progress?language_id=&tz=` con resumen, destrezas, errores frecuentes e historial, todo
      derivado de conversaciones, intentos, correcciones y vocabulario guardados en F3–F5.
- [x] Nivel como dato del perfil, de solo lectura; se cambia solo en `/languages` con acción explícita.
- [x] Sin esquema nuevo ni migración: la vista es de solo lectura.
- [x] PWA: resumen, cinco destrezas (tres con señal real; lectura y escucha como «sin datos»), errores
      frecuentes e historial con enlaces reales.
- [x] Contrato en `docs/api-contract.md` §3 «El progreso» y ADR-018.
- [x] `uv run pytest`, `ruff check`, `ruff format --check`, `npm run typecheck` y `npm run build`
      ejecutados y verdes.

**Verificación ejecutada:**

- `uv run pytest` → **221 passed in 34.28s** (incluye los 12 escenarios de `/progress`, los 5 de
  `week_start` y las 203 pruebas previas).
- `uv run ruff format --check` y `uv run ruff check` → limpios (3 archivos nuevos formateados antes).
- `npm run typecheck` → exit 0; `npm run build` → ✓ built in 2.68s.
- Sonda HTTP contra una base **aislada**, migrada con Alembic y sembrada, en el puerto 8010:
  francés `1/4` lecciones, 1 conversación, `writing: 3`, 3 errores frecuentes y 3 filas de historial;
  una conversación alemana nueva cuenta como 1 en la meta semanal y **no** contamina la meta francesa;
  `tz=No/Existe` → 400 `invalid_timezone`; idioma inexistente → 404 `language_not_found`.
- Sonda de navegador con Chromium headless (Playwright) sobre la PWA real en 1280×900 y 375×812:
  la pantalla muestra resumen, cinco destrezas, errores e historial; no hubo errores de consola ni
  desborde horizontal; las llamadas salieron por `http://127.0.0.1:5173/api/v1/...`, es decir por el
  proxy de Vite, no contra `localhost:8000` del navegador.
- URL pública de Codespaces (`https://<codespace>-5173.app.github.dev`) verificada de punta a punta:
  la app devolvió 200 y `/api/v1/health` y `/api/v1/progress` respondieron a través del proxy. Se
  probó con visibilidad temporal `public` y se volvió a `private`.

**Entorno Codespaces.** Para que la URL pública funcione hicieron falta dos ajustes locales:
`allowedHosts: [".app.github.dev"]` en `server` y `preview` de `frontend/vite.config.ts`, y
`VITE_API_BASE_URL=/api/v1` en `frontend/.env.local` (ignorado por git). El puerto 5173 se registró
con `gh codespace ports forward 5173:15173`.

**Límites conocidos:** no hay minutos ni «tiempo practicado» porque no se registra duración
(ADR-018); lectura y escucha no tienen señal y no se muestran como cero; el frontend sigue sin suite
propia porque el stack de testing no está decidido (`docs/stack.md`); `npm audit` reporta 4
vulnerabilidades (3 moderadas, 1 alta) en dependencias de desarrollo, sin `npm audit fix` para no
cambiar versiones fuera de esta fase.

## F6.5 — UI inteligente en el chat — **completada**

Alcance, contrato y evidencia: `odd/tasks/chat-ui-blocks.md`. Decisión registrada: ADR-020.

- [x] Bloques de práctica tipados en el turno del tutor (`phrase`, `drill`), validados en el
      dominio con límites duros: 2 por turno, uno interactivo, árbol chato.
- [x] El cierre de turno (`feedback.v2`) propone contenido; la API valida y la PWA dibuja. El modelo
      no elige componentes ni layout, y no hay acoplamiento al harness (ADR-004).
- [x] Evento SSE `blocks` después de `message_end` y antes de `correction`/`vocabulary`; bloques
      persistidos con el mensaje y devueltos por el detalle.
- [x] `POST .../blocks/{block_id}/answers` con corrección determinista y sin persistir intentos; las
      respuestas aceptadas no viajan al cliente antes de responder.
- [x] PWA: tarjeta de frase con audio (F4) y ejercicio interactivo con «Comprobar», fallback visible
      ante un `kind` desconocido.

**Verificación:** `uv run pytest` (267 passed), `ruff format --check` y `ruff check` limpios,
`npm run typecheck` y `npm run build` verdes; un turno real contra el adaptador de OpenCode devolvió
`blocks` con `phrase` + `drill`, el ejercicio se corrigió bien y mal por HTTP, y los bloques
sobrevivieron a la reedición del detalle. Detalle en el documento de la fase.

**Límites conocidos:** el resultado del drill no se guarda (no suma señal a `/progress`, ADR-018); el
frontend sigue sin suite propia porque el stack de testing no está decidido (`docs/stack.md`); la
frase no trae traducción propia y `desing.md` §6.1.2 todavía no menciona los bloques (propuesta de
texto pendiente de aprobación del humano).

## F6.6 — Lecciones con ejercicios de elección — **completada**

Alcance y evidencia: `odd/tasks/lesson-choice-exercises.md`. Decisión registrada: ADR-021.

- [x] `LessonExercise.kind` (`writing` | `choice`) y `options`, aditivos y con default `writing`.
- [x] Corrección única: la opción elegida se compara con el mismo `domain/grading.py` de un
      ejercicio escrito; las respuestas aceptadas y la opción correcta no viajan al cliente.
- [x] Catálogo sembrado con un `choice` por idioma (inglés, francés y alemán).
- [x] PWA: grupo de radios de ancho completo, contador de respondidos y resultado igual al de un
      ejercicio escrito.
- [x] Contrato, ADR y este roadmap actualizados.

**Verificación:** `uv run pytest` (273 passed), `ruff format --check` y `ruff check` limpios,
`npm run typecheck` y `npm run build` verdes; sonda HTTP sobre una base limpia migrada y sembrada:
el detalle devolvió `kind`/`options`, elegir la opción equivocada dio 3/4 con la esperada revelada, y
la correcta 4/4 completada.

**Límites conocidos:** el seed no refresca un catálogo ya sembrado, así que una base anterior no ve
los ejercicios nuevos sin recrearla; `order` y `listen` siguen siendo decisiones aparte; el frontend
continúa sin suite propia (`docs/stack.md`).

## F7 — Intérprete en tiempo real — **completada** (rama `feat/f7-live-interpreter`)

Alcance, contrato y evidencia: [`odd/tasks/f7-live-interpreter.md`](../odd/tasks/f7-live-interpreter.md).
Decisión registrada: ADR-022.

- [x] `WS /voice/interpret` con PCM 16 kHz, ventanas de 4,5 s, solape de 0,5 s y deduplicación.
- [x] Whistle en streaming por ventanas (T0 midió el corte de ~5 s); el motor no bloquea el event loop.
- [x] Traducción de parciales y segmentos finales con el mismo proveedor; la final es autoritativa.
- [x] Modo texto real en `/translate` y PWA del intérprete con estados, historial efímero y aviso de latencia.
- [x] `OPENCODE_TRANSLATION_AGENT=general` para que la traducción no narre el rol de `plan`.
- [x] Contrato, ADR, stack y este roadmap actualizados.

**Verificación:** `uv run pytest` 292 passed; Ruff, typecheck y build verdes; WS real con un clip
humano de 11 s (segmentos a 2–4 s, traducciones a 7–12 s); sonda de navegador a 1280×900 y 375×812
con micrófono falso, sin errores de consola ni desborde.

**Límites conocidos:** el proveedor tarda 3–7 s por traducción, así que los parciales suelen quedar
viejos; el corte de 4,5 s puede degradar un segmento corto; el TTS de la traducción queda fuera; no
hay suite de frontend; a 375 px el saludo del TopBar se parte en cuatro líneas (deuda de F1).

## Fuera de alcance

Pagos, gamificación extensa, redes sociales, marketplace, personajes 3D, analíticas complejas, identidad de marca definitiva
(`desing.md` §13).
