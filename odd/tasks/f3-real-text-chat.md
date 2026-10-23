# F3 — Chat de texto real

Fase F3 de `docs/roadmap.md`. Rama: `feat/f3-real-text-chat` (apilada sobre `feat/f2-backend-skeleton`, sin mergear a `main`).
Autorizado por el humano en L1; las cuatro decisiones que bloqueaban la fase se eligieron en L2.

## Specs

**S1 — Motor del tutor: una instancia de Pi (L2.1).** Literal del humano: «lo que quiero es una instancia de pi».
El puerto `LLM` se implementa con un adaptador que lanza `pi --print --mode json` como subproceso, sin SDK de
terceros, sin claves nuevas y sin depender de un proveedor cloud propio. La invocación fija `--no-session`,
`--no-tools`, `--no-builtin-tools`, `--no-context-files`, `--no-extensions`, `--no-skills`, `--no-mcp` y un
directorio de trabajo neutro: el tutor es texto, no un agente con acceso al sistema. El binario y el modelo son
configurables (`PI_BIN_PATH`, `PI_MODEL`); con `PI_MODEL` vacío se usa el default de la máquina (L2.4, opción
«turno real contra el Pi local»).

**S2 — Puerto `LLM` en `ports/`, adaptador en `adapters/`.** `docs/architecture.md` §3: «`application/` depende de
`ports/`, nunca de `adapters/` concretos». El dominio y los casos de uso no importan `subprocess`, `asyncio`, JSON
de la CLI ni nada de Pi. El contrato del puerto: transmitir la respuesta del tutor por partes y producir el cierre
del turno (correcciones + vocabulario) con una operación separada.

**S3 — Prompt del tutor versionado en el repo.** Literal del roadmap: «Puerto `LLM` + primer adaptador; prompt del
tutor versionado». El prompt vive en `backend/app/adapters/llm/prompts/`, con versión explícita en el archivo y en
una constante; recibe idioma objetivo, nivel CEFR e idioma de explicación del `LanguageProfile`, y produce
contenido educativo en el idioma que se estudia con explicaciones en `explanation_language` (AGENTS.md §3 y
`desing.md` §6.6). Los textos visibles de la interfaz siguen en español; el contenido educativo es el del idioma.

**S4 — `POST /conversations/{id}/messages` persiste el mensaje del usuario y no duplica turnos.**
`docs/api-contract.md` §3 ya lo marca F3; §1 pide `Idempotency-Key` «cuando el reintento duplicaría un turno» y
`docs/architecture.md` §5 lo exige. Un reintento con la misma clave devuelve el mensaje ya persistido, no un
duplicado. Un `message_id` que no pertenece a la conversación, o un mensaje que no es del usuario, se rechaza.

**S5 — Streaming SSE del turno, según el contrato (L2.3).** Opción elegida: «Confirmar el contrato: POST + GET SSE».
`GET /conversations/{id}/stream?message_id=` transmite, en este orden: `token` (delta de texto), `message_end`
(mensaje del tutor autoritativo), `correction` (correcciones del mensaje del usuario), `vocabulary` (términos
sugeridos) y `error` (sobre del contrato §4). Los eventos nuevos que el contrato no listaba se agregan a
`docs/api-contract.md` en el mismo commit que los introduce. El servidor cierra el stream al terminar.

**S6 — Cancelación real.** `docs/architecture.md` §5: «si el usuario corta la reproducción o abandona el turno, se
cancela la llamada al proveedor». Cerrar el stream mata el subproceso de Pi, persiste lo emitido con estado
`error`, no emite un `message_end` de éxito y no deja procesos huérfanos. Un turno cancelado no bloquea el
siguiente.

**S7 — Correcciones y vocabulario al cerrar el turno, persistidos.** Literal del roadmap: «Correcciones y
vocabulario sugerido al cerrar el turno». Opción elegida (L2.2): tablas nuevas, no una columna JSON ni eventos
efímeros. `message_feedback` (1:1 con el mensaje del usuario), `message_corrections` y `vocabulary_items` (con
`language_id`), migración de Alembic incluida. El detalle de la conversación devuelve el feedback del mensaje del
usuario para que sobreviva a una recarga. Si el cierre del turno falla, el chat no se rompe: el texto del tutor ya
está persistido y el feedback se omite.

**S8 — Datos aislados por idioma.** AGENTS.md §3: «Toda consulta de conversaciones, lecciones, planes y progreso se
filtra por `language_id`». El turno usa el idioma de la conversación, no el idioma activo global; el vocabulario
guardado lleva `language_id`; abrir una conversación de otro idioma no mezcla historial ni feedback.

**S9 — La PWA conversa de verdad.** `desing.md` §6.1.2 y `docs/roadmap.md` §F3: enviar por texto muestra la
respuesta del tutor en streaming, con el estado «Pensando…» visible mientras dura, botón de cancelar mientras
transcurre, correcciones y vocabulario como tarjetas del turno, y error con «Reintentar». El aviso de prototipo
del compositor («el envío llega en F3») desaparece porque el tutor ya responde; ningún control decorativo nuevo.
Los botones de voz siguen explícitamente deshabilitados hasta F4.

**S10 — Contrato y documentación al día.** `docs/api-contract.md` documenta el turno, los eventos SSE y los campos
nuevos de `Message`; `docs/decisions.md` registra ADR-013 (Pi como motor del tutor); `docs/stack.md` mueve a
**Decidido** las filas de motor del tutor y streaming de texto; `docs/roadmap.md` marca F3; `docs/env.example`
documenta `PI_BIN_PATH`, `PI_MODEL` y `PI_TIMEOUT_SECONDS`.

**S11 — Sin regresiones de F1/F2.** La suite existente sigue verde, `/languages` y `/conversations` mantienen su
comportamiento, y el typecheck y el build del frontend siguen limpios. Todo cambio de contrato es aditivo.

## Assumptions

- El historial se reenvía en cada turno y Pi corre con `--no-session`: la base es la única fuente de verdad y la
  API sigue sin estado (`docs/architecture.md` §6).
- El modelo del turno es el default del Pi instalado; `PI_MODEL` permite fijarlo sin cambiar código.
- El cierre del turno es una segunda invocación corta de Pi con salida JSON; su latencia no bloquea el texto ya
  emitido.
- Los tests usan un doble determinista de `LLM`; el turno real contra Pi se verifica aparte (E2E manual documentado),
  porque la suite no puede depender de red, credenciales ni de un modelo concreto.
- El subproceso se ejecuta con `--no-tools` y cwd neutro: el tutor no lee ni escribe archivos del repositorio.
- Los ids siguen siendo UUID v4 en `String(36)` y los tipos siguen siendo portables (ADR-012).

## Tasks

| ID | Qué | Specs | Estado | Commit |
|---|---|---|---|---|
| T1 | Puerto `LLM`, adaptador Pi (JSONL + cancelación), prompts del tutor y de cierre versionados, doble de test | S1, S2, S3 | hecho | `f05d820` |
| T2 | Turno persistido: `idempotency_key`, repositorios, caso de uso `send_message`, `POST /messages` | S4, S8 | hecho | `1cce152` |
| T3 | SSE del turno: `GET /stream`, mapeo de deltas a `token`, `message_end`, cancelación y estado `error` | S5, S6 | hecho | `64abc10` |
| T4 | Cierre de turno: extracción estructurada, persistencia de correcciones y vocabulario, eventos `correction`/`vocabulary`, feedback en el detalle | S7, S8 | hecho | `8accbf3` |
| T5 | Frontend real: cliente SSE, compositor contra la API, «Pensando…», cancelar, tarjetas de corrección y vocabulario, reintento | S9 | hecho | `a3a62e2` |
| T6 | Docs y verificación de la fase: ADR-013, contrato, stack, roadmap, env; pytest, ruff, typecheck, build, E2E real contra Pi, sonda en navegador y verificación independiente de seguridad | S10, S11 | hecho | este commit |

## Log

**L1** — Pedido original, literal:

> vamos con F3

Contexto: `docs/roadmap.md` §F3 define la fase («Puerto `LLM` + primer adaptador; prompt del tutor versionado.
Streaming SSE del turno, con cancelación. Correcciones y vocabulario sugerido al cerrar el turno. Verificación:
conversación real por texto, con historial y cambio de idioma sin mezclar datos.») y el estado de partida es F2
cerrada en `feat/f2-backend-skeleton`.

**L2** — Cuatro decisiones elegidas por el humano antes de escribir código:

1. Motor del tutor — **una instancia de Pi**: «lo que quiero es una instancia de pi».
2. Correcciones y vocabulario — **tablas nuevas** (`message_feedback` 1:1, correcciones y vocabulario con
   `language_id`), no una columna JSON ni eventos efímeros.
3. Transporte — **confirmar el contrato**: `POST /messages` + `GET /stream?message_id=` SSE, con cancelación al
   cerrar el stream.
4. Verificación del turno — **«Sí: turno real contra el Pi local»**: el E2E lanza una instancia real de Pi con el
   modelo y las credenciales ya configurados en la máquina; los tests usan además un doble determinista.

**L3** — Entorno verificado antes de elegir: `uv 0.11.23`, Python 3.14.4, Node 24.19.0, `pi 1.3.0` en
`~/.local/bin/pi`, sin `.env` y sin claves de proveedores en el entorno. `docs/stack.md` tenía «Motor del tutor» y
«Streaming de texto» en **Pendiente**; ambas quedan decididas por L2 y se registran como ADR-013.

**L4** — Interfaz de Pi usada: `--print --mode json` emite JSONL con `message_update`
(`assistantMessageEvent.type == "text_delta"`), `message_end` autoritativo y `agent_settled`
(`docs/json.md` del paquete `pi-coding-agent` 1.3.0). El adaptador no usa el SDK TypeScript porque el backend es
Python; es un subproceso con parser JSONL propio.

**L5** — Riesgo de seguridad declarado: el adaptador ejecuta un binario externo por turno. Se acota con
`--no-tools`, `--no-builtin-tools`, `--no-session`, `--no-context-files`, `--no-extensions`, `--no-skills`,
`--no-mcp`, cwd neutro y timeout propio. Es un ítem de riesgo 2 y por eso la fase cierra con verificación
independiente.

**L7** — T4 resultó una unidad grande (~1.650 líneas, la mitad tests del worker): un solo commit para la migración, el
parser, el wiring y el detalle. Es revisable por partes aunque no por el techo cómodo; si el humano pide review nativo,
el slice se toma por unidad funcional, no por el acumulado de la rama. Los tests nuevos mordieron: guardar el feedback
contra el mensaje del tutor rompió 4 de los 9 tests de integración.

**L6** — Frontera de slices: la rama está apilada sobre `feat/f2-backend-skeleton`, que a su vez incluye F1, así
que el diff contra `main` suma las tres fases (el harness reportó ~9,4k líneas después de T1). Lo que cuenta como
slice de F3 es cada unidad: T1 = 826 líneas, T2 = 276 líneas, y así las siguientes. Ningún commit de F3 supera el
techo cómodo de revisión por sí solo.

**L8** — Verificación real contra Pi (T6). Con el adapter real y una base migrada por Alembic, el turno completo
funciona de punta a punta: 4 `token` a los 4 s, `message_end` a los 7 s, `correction` y `vocabulary` a los 14 s (la
corrección real fue «the» → «thé»), y el feedback queda persistido y visible en `GET /conversations/{id}`. El turno
en inglés, con otra conversación y otro idioma, respondió en inglés con `message_end` a los 7 s y `vocabulary` a los
14 s, sin correcciones porque la frase no tenía errores; ningún dato del francés apareció en esa conversación.

Dos de los primeros intentos lanzados contra uvicorn se cortaron a los 60 s sin un solo token. No es un defecto
determinista: el adapter aislado respondió en 6,5 s (asyncio) y 7,8 s (uvloop), `TestClient` con el mismo código,
base y adapter respondió al primer token en 4,8 s, y turnos posteriores en el mismo servidor respondieron en 14 s.
El patrón es un arranque lento intermitente del proveedor por encima del presupuesto de 60 s del contrato
(`docs/api-contract.md` §5). El comportamiento ante ese fallo es el esperado y accionable: evento `error` con
`llm_timeout`, mensaje del tutor en `error` y «Reintentar» en la UI; el reintento funcionó. El presupuesto no se
cambia sin evidencia de que haga falta.

**L9** — La corrida real dejó un defecto que la suite no veía: un turno fallido sin tokens guarda un mensaje del
tutor en `error` con `content=""`, y ese mensaje entraba al historial del turno siguiente como un turno vacío del
tutor. Se filtra el historial a mensajes con contenido (el mensaje del estudiante siempre viaja) y se pinea con
`test_a_failed_turn_without_text_never_reaches_the_next_prompt`; el fix se commitea aparte.

**L10** — Verificación independiente de seguridad (ítem de riesgo 2). Un verificador read-only revisó el aislamiento del
subproceso y encontró cuatro defectos reales, todos corregidos en `f11c534` con tests que primero fallaron: el
presupuesto del turno no cubría el arranque ni la entrega del prompt; faltaban `--no-prompt-templates` y
`--no-approve`; la cancelación mataba el proceso pero no su grupo; y una respuesta desmedida se guardaba entera. El
subproceso ahora corre en su propia sesión, el timeout envuelve toda la invocación, la respuesta se corta a 20 000
caracteres y no se loguean payloads del proveedor. Quedó abierto, por decisión y documentado: un subproceso por turno
sin límite de concurrencia, aceptable mientras la API sea local y sin auth (ADR-012), a revisar antes de exponerla.

**L11** — T5 (frontend) entrega el cliente SSE sobre `fetch` (sin `EventSource`: no puede mandar `Idempotency-Key` ni
cancelar), la máquina de turnos `sending → streaming → done | error`, «Pensando…», «Detener», reintento con la misma
clave y tarjetas de corrección y vocabulario. Sin dependencias nuevas y sin runner de tests en el frontend: la
verificación ejecutable es `typecheck` y `build` (verdes) más un smoke del parser SSE; el comportamiento real se
verifica en la sonda de navegador y en el E2E de API.

**L12** — Sonda de navegador real (Chrome headless por DevTools Protocol, backend uvicorn en `:8000` sobre la base
migrada, Vite dev en `:5173`). La sonda cargó `/chat/9a4b6c81-…-4c02`, escribió un turno y lo envió con `Enter`, y
observó el DOM en tiempo real: hilo del seed cargado, mensaje del usuario en el hilo, «Pensando…» visible antes del
primer token, 70 caracteres del tutor en streaming, botón «Detener» presente mientras duraba el stream, y las tarjetas
de corrección y vocabulario al cierre. Respuesta final: «Très bien, un thé. Vous voulez du lait avec ?». Sin estado de
error. El intento previo con `--dump-dom` y `--virtual-time-budget` falló porque el tiempo virtual no espera la red
real: se descartó como herramienta de verificación de este flujo.

**L13** — Cierre de la fase: commits de F3 en la rama `feat/f3-real-text-chat` — T1 `f05d820`, T2 `1cce152`, T3
`64abc10`, T4 `8accbf3`, fix del historial `4414e63`, hardening de seguridad `f11c534`, más los commits de frontend
y docs. La rama queda apilada sobre `feat/f2-backend-skeleton` y `feat/f1-pwa-shell`, sin mergear a `main`: integrar
las tres es decisión del humano. Límites conocidos y condiciones a revisar documentados en L8 (arranque lento
intermitente del proveedor frente al presupuesto de 60 s) y L10 (un subproceso por turno sin límite de concurrencia,
mientras la API sea local y sin auth).
