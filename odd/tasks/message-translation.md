# Traducción de mensajes y fragmentos

Feature previa a F4 (voz). Rama de trabajo: `feat/f3-real-text-chat` (F3 sin mergear).
**Sin commits**: `AGENTS.md` §6.7 lo prohíbe salvo pedido explícito. Autorizada en L1; las dos
decisiones que la bloqueaban se resolvieron en L2.

## Specs

**S1 — «Traducir» traduce el mensaje completo o solo el fragmento seleccionado.** Literal del humano:
«incluso quisiera que puesda seleccionar una parte del texto y que eso sea lo que se tradusca , para
que no sea completo». Disparo elegido en L2 (Flujo C, «Solo el botón del mensaje»): no hay UI
flotante; el botón «Traducir» de las acciones del mensaje mira la selección activa **dentro de la
burbuja de ese mensaje**. Sin selección traduce el mensaje entero; con selección traduce solo ese
fragmento. El fragmento se recorta y se descarta si queda vacío. Nada de botones decorativos: la
acción siempre traduce algo (desing.md §8).

**S2 — La traducción del mensaje completo se persiste; la del fragmento no.** La columna
`messages.translation` ya existe (`backend/app/adapters/db/models.py:59`) y el contrato ya expone
`translation` en `Message` (`docs/api-contract.md` §2), así que la traducción del mensaje sobrevive
a una recarga sin migración. La del fragmento es efímera: vive en el estado del componente y no se
guarda, porque no hay a quién pertenecer (el fragmento no es una entidad).

**S3 — Dirección por idioma de la conversación, nunca por el idioma activo global.** Origen: `code`
del `LanguageProfile` dueño de la conversación. Destino: `explanation_language` de ese mismo perfil
(AGENTS.md §3, «datos por idioma»; desing.md §6.6, «idioma de explicación»). Pedir una traducción
desde una conversación de otro idioma no puede usar el contexto activo.

**S4 — Contrato: un endpoint para el fragmento y otro para el mensaje persistido.**
`POST /translate` ya está en `docs/api-contract.md` §3 y sigue siendo el camino *stateless* del
fragmento. Se agrega `POST /conversations/{id}/messages/{message_id}/translation`, que traduce y
persiste el mensaje completo y es **idempotente**: si el mensaje ya tiene traducción guardada la
devuelve sin llamar al proveedor. Los dos endpoints actualizan `docs/api-contract.md` en el mismo
commit (AGENTS.md §6.4).

**S5 — La traducción pasa por el puerto `LLM` y un prompt versionado.** Sin SDK nuevo ni proveedor
aparte: el adaptador de Pi gana una operación de traducción y el prompt vive en
`backend/app/adapters/llm/prompts/translate.v1.md`, con su versión afirmada por un test
(ADR-014). Un fallo del proveedor responde el sobre de error del contrato con `llm_unavailable`
(502) o `llm_timeout` (504).

**S6 — Estados visibles en la burbuja.** Mientras traduce, el botón queda deshabilitado y la burbuja
dice «Traduciendo…»; si falla, se muestra el error con «Reintentar»; con traducción abierta, el
botón dice «Ocultar traducción» (`aria-pressed`). Cuando se tradujo un fragmento, el panel cita el
fragmento y después la traducción, para que no se confunda con el mensaje completo.

**S7 — `desing.md` documenta la traducción por selección.** Autorizado en L2: se agregan las dos
líneas de §6.1.2 y §8 que describen el comportamiento (AGENTS.md §7 lo exige explícito).

## Tasks

| ID | Specs | Ruta | Commit |
|---|---|---|---|
| T1 | S5 | Prompt `translate.v1` + operación de traducción en `ports/llm.py` y en el adaptador de Pi, con tests unitarios | sin commit |
| T2 | S2, S3 | `application/translation.py` + `set_translation` en el repositorio de mensajes, con tests | sin commit |
| T3 | S4 | Rutas `/translate` y `/conversations/{id}/messages/{message_id}/translation`, esquemas y errores | sin commit |
| T4 | S1, S6 | Cliente web de traducción, comportamiento de selección en `ChatMessage` y estilos | sin commit |
| T5 | S7, S4 | `desing.md`, `docs/api-contract.md`, `docs/decisions.md` (ADR-014), `docs/stack.md`, `docs/roadmap.md` | sin commit |
| T6 | todas | `uv run pytest`, `ruff format --check`, `ruff check`, `npm run typecheck`, `npm run build` y turno real de traducción contra el Pi local | — |

## Log

**L1 — pedido original, literal:**

> perfecto vamos con eso y esto https://huggingface.co/Cactus-Compute/whistle para el stt pero antes
> vamos a habilitar las traducciones de las respuestas , incluso quisiera que puesda seleccionar una
> parte del texto y que eso sea lo que se tradusca , para que no sea completo

**L2 — decisiones de producto (preguntas del orquestador, respuestas del humano):**

1. Disparo de la traducción por selección: «Solo el botón del mensaje» (Flujo C): sin burbuja
   flotante; el botón «Traducir» detecta la selección dentro de ese mensaje y traduce solo eso, o
   el mensaje completo si no hay selección.
2. Permiso sobre `desing.md`: «Sí: actualizá §6.1.2 y §8».

**L3 — F4 queda para después de esta feature.** El humano confirmó el modelo STT en L1
(Whistle, `https://huggingface.co/Cactus-Compute/whistle`); se registra al abrir la feature de voz.

## Verificación

| Qué | Cómo | Resultado |
|---|---|---|
| Backend | `uv run pytest` | **123 passed** |
| Formato y lint | `uv run ruff format --check` y `uv run ruff check` | limpios |
| Frontend | `npm run typecheck` y `npm run build` | verdes |
| Traducción real de un fragmento | API real + `pi` real: `POST /translate` `{"text":"Qu'est-ce que vous aimeriez prendre ?","source":"fr","target":"es"}` | `{"translation":"¿Qué le gustaría tomar?","detected_source":"fr"}` en 10,4 s |
| Traducción real de un mensaje | `POST /conversations/{id}/messages/{id}/translation` y después `GET` del detalle | traducción guardada y devuelta por el detalle; segunda llamada en 0,015 s respondida desde la base |
| Entrada vacía | `POST /translate` con `text: "   "` | 422 `validation_error`, sin llamar al proveedor |
| UI real (Chrome headless por CDP) | selección de `Bonjour !` dentro de la burbuja, `mouseup`, click en «Traducir» | panel con «Bonjour !» → «¡Hola!» en 5,6 s; «Ocultar traducción» cierra en 2 ms; el mensaje completo sale de la base en 30 ms |
| Persistencia en la UI | recargar la conversación y volver a pulsar «Traducir» | misma traducción en 3 ms, **sin** ninguna llamada a la API |
| Mensaje completo desde la UI | mensaje en inglés «Hi! Ready to practise?…» sin traducción guardada | «¡Hola! ¿Listo para practicar? Contame cómo ha ido tu día hasta ahora.» en 7,6 s, y tras recargar aparece en 4 ms |

**Límites de la verificación, dichos y no escondidos:** la selección del navegador se hizo por DOM
(`Range` + `mouseup`), no con el mouse real; el camino de error («No pudimos traducir.» / «Reintentar»)
no se ejercitó en el navegador, solo en el test de integración del 502 y en el código del componente.
Cada traducción real cuesta una invocación completa de Pi: entre 5 y 15 segundos la primera vez.
