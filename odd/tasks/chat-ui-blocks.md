# F6.5 — UI inteligente en el chat

Fase F6.5 de `docs/roadmap.md`, insertada antes de F7 por pedido del humano: el chat y las lecciones
deben usar la idea de «interfaz inteligente» del proyecto pixelUI, de forma sencilla y útil para
aprender. Checks ejecutados: `uv run pytest`, `uv run ruff check`, `uv run ruff format --check`,
`npm run typecheck` y `npm run build`.

## Decisiones del humano (L1)

1. Alcance de la primera entrega: **chat primero**, con dos bloques; las lecciones reutilizan después
   el mismo renderer.
2. Transporte: **extender el cierre de turno existente**, sin una tercera llamada al proveedor.
3. Bloques de v1: **frase practicable** y **mini-ejercicio**.
4. El mini-ejercicio se responde en un **endpoint dedicado, sin persistir** el intento.

Quedaron fuera de v1, explícitamente: escenario de roleplay, gráficos/tablas, HTML libre y cualquier
mecanismo donde el modelo elija el componente.

## Specs

**S1 — El turno del tutor puede traer práctica, no solo prosa.** Literal de `desing.md` §6.1.2:

> - Respuestas del tutor pueden incluir **audio, ejercicios, traducciones, correcciones o tarjetas de
>   vocabulario**.

Hasta F6 solo correcciones y vocabulario eran estructurados. Se agregan bloques tipados al mensaje
del **tutor**: `phrase` (una frase para escuchar) y `drill` (una pregunta). El árbol es chato y
acotado: 0 a 2 bloques, como máximo uno interactivo. El bloque complementa el texto; nunca lo
reemplaza.

**S2 — El modelo propone contenido, no interfaz.** El proyecto pixelUI inspira la idea, pero su
mecanismo (`render_ui` como tool del harness) no se copia: `desing.md` §12 y ADR-004 exigen que la UI
no conozca el harness. El modelo llena campos de tipos conocidos; `domain/blocks.py` valida y aplica
los límites, y la PWA decide cómo se dibuja cada `kind`. Un `kind` desconocido se anuncia como no
disponible y no rompe el hilo.

**S3 — Los bloques llegan en el cierre de turno y sobreviven a la recarga.** `feedback.v2` devuelve
correcciones, vocabulario y bloques en una sola invocación. El evento SSE `blocks` sale **después** de
`message_end` y **antes** de `correction`/`vocabulary`, con el `message_id` del tutor. Se guardan con
el mensaje (`messages.blocks_json`) y `GET /conversations/{id}` los devuelve.

**S4 — Un ejercicio se corrige igual que una lección, y sin filtrar la respuesta.**
`POST /conversations/{id}/messages/{message_id}/blocks/{block_id}/answers` usa
`domain/grading.py` (las mismas reglas de ADR-017: mayúsculas, puntuación y espacios no cuentan; los
acentos sí). Las respuestas aceptadas y la explicación no viajan al cliente antes de responder, y
`expected` solo se revela tras un fallo. El intento no se guarda: `/progress` sigue derivando de las
señales de ADR-018.

**S5 — La frase se escucha sin trabajo nuevo de audio.** La tarjeta reutiliza el «Escuchar / Más
lento» de F4: la síntesis ya existe y se pide por contenido. El audio no se guarda.

**S6 — Nada de dashboard.** Sin gráficos, tablas, métricas ni rachas: ADR-018 prohíbe inventar
mediciones y `desing.md` §2 pide que el chat siga siendo el centro.

## Implementación

| Capa | Archivos |
|---|---|
| Dominio | `backend/app/domain/blocks.py` (tipos, límites, `public`, storage, `grade_drill`) |
| Puerto | `backend/app/ports/llm.py` (`TurnFeedback.blocks`) |
| Parseo | `backend/app/adapters/llm/parsing.py` (bloques opcionales, tolerantes) |
| Prompt | `backend/app/adapters/llm/prompts/feedback.v2.md` |
| Caso de uso | `backend/app/application/tutor.py` (`TurnBlocksReady`, cierre parcial), `backend/app/application/blocks.py` |
| Persistencia | `messages.blocks_json` + migración `e6a4b8c2d1f3` |
| API | `Message.blocks`, evento `blocks`, endpoint de respuestas, códigos `block_not_found` / `block_not_answerable` |
| PWA | `frontend/src/features/chat/blocks/TurnBlocks.tsx`, `lib/api/blocks.ts`, tipos y mapeo en `ChatPage.tsx` |

El cierre de turno persiste bloques y feedback por separado: si falla una escritura, la otra se
intenta igual y los eventos solo anuncian lo que quedó guardado.

## Verificación ejecutada

- `uv run pytest` → **267 passed** (27 nuevos: 16 de dominio, 11 de API).
- `uv run ruff format --check` y `uv run ruff check` → limpios.
- `npm run typecheck` → exit 0; `npm run build` → ✓ built in 2.08s.
- Turno real contra `LLM_PROVIDER=opencode` sobre una base aislada migrada y sembrada: el stream
  emitió `token`, `message_end`, `blocks` (una `phrase` y un `drill`), `correction` y `vocabulary`,
  en ese orden.
- Respuesta al drill por HTTP: una respuesta con acentos y apóstrofos tipográficos → `correct: true`,
  `expected: null`; una respuesta sin el circunflejo («plait» por «plaît») → `correct: false` con la
  respuesta esperada; responder la `phrase` → 400 `block_not_answerable`.
- `GET /conversations/{id}` devolvió los bloques con el mensaje del tutor y `[]` en los del usuario.

## Límites conocidos

- El drill no se persiste: al recargar vuelve a estar sin responder y no suma señal a `/progress`
  (ADR-020, ADR-018).
- El frontend no tiene suite propia: `docs/stack.md` sigue sin decidir el stack de testing. La
  interacción se verificó por contrato (API) y por `typecheck`/`build`, no con un test de componente.
- La tarjeta de frase no trae traducción propia; el botón «Traducir» del mensaje sigue cubriéndola.
- `desing.md` §6.1.2 todavía no menciona los bloques: el texto propuesto está en el reporte de la
  fase y espera aprobación del humano.
