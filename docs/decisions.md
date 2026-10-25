# Decisiones — Polybot

Formato liviano de ADR: contexto, decisión, consecuencias.
Solo entran decisiones confirmadas por el humano. Las propuestas viven en `docs/stack.md` §Pendiente.

---

## ADR-001 — Monolito modular como forma inicial

**Estado:** aceptada · **Fecha:** 2026-10-22

**Contexto.** Producto nuevo, un solo desarrollador asistido por agentes. Se pidió "algo escalable" sin tráfico real todavía.

**Decisión.** Un backend FastAPI con capas explícitas (`domain`, `application`, `ports`, `adapters`) y una PWA independiente. Sin microservicios.

**Consecuencias.** Se gana velocidad y un modelo mental simple. La escalabilidad queda en procesos sin estado y límites de carpetas, no en la topología. Si un adaptador (STT, TTS) necesita escalar aparte, la frontera de `ports/` ya permite extraerlo sin reescribir el dominio.

---

## ADR-002 — FastAPI como framework del backend

**Estado:** aceptada · **Fecha:** 2026-10-22

**Contexto.** Se necesita API tipada, asíncrona, con streaming y documentación automática; el equipo conoce Python.

**Decisión.** FastAPI sobre Python 3.12+.

**Consecuencias.** OpenAPI gratis para generar tipos del frontend. Exige disciplina para no meter lógica en routers y para no bloquear el event loop con TTS/STT.

---

## ADR-003 — Piper para texto a audio

**Estado:** aceptada · **Fecha:** 2026-10-22

**Contexto.** Se necesita síntesis de voz local, rápida y multiplataforma, con varias voces por idioma.

**Decisión.** Piper como motor TTS, detrás del puerto `TTS`.

**Consecuencias.** Síntesis local, sin costo por carácter y sin dependencia de la nube. Consume CPU: requiere cola y límite de concurrencia. Las voces se descargan y versionan aparte del código.

---

## ADR-004 — Frontend independiente del harness del agente

**Estado:** aceptada · **Fecha:** 2026-10-22

**Contexto.** `desing.md` §12 pide que la UI no quede acoplada a Pi, OpenCode ni a ningún orquestador.

**Decisión.** La PWA solo consume HTTP/SSE. El tutor es un caso de uso del backend; el harness que ejecute el modelo es un detalle del adaptador `LLM`.

**Consecuencias.** Cambiar de proveedor o de harness no toca la UI. Exige un contrato de API estable y un prompt del tutor versionado en el repo.

---

## ADR-005 — Español como idioma de la interfaz

**Estado:** aceptada · **Fecha:** 2026-10-22

**Contexto.** El wireframe y todo el diseño están escritos en español.

**Decisión.** UI y mensajes de error en español; código y documentación técnica interna en inglés (ver `conventions.md` §1).

**Consecuencias.** Los textos visibles viven centralizados para permitir internacionalización futura sin reescribir componentes.

---

## ADR-006 — Sin promesa de offline conversacional

**Estado:** aceptada · **Fecha:** 2026-10-22

**Contexto.** `desing.md` §9 aclara que la app puede instalarse pero no hay modelos locales garantizados.

**Decisión.** La carcasa de la PWA funciona offline; conversación, traducción y voz requieren red en v1. La UI lo comunica con un estado visible.

**Consecuencias.** Evita una promesa que el producto no puede cumplir. Si más adelante se agregan modelos locales, se revisa esta decisión.

---

## ADR-007 — Wireframe monocromático antes que identidad de marca

**Estado:** aceptada · **Fecha:** 2026-10-22

**Contexto.** `desing.md` §3 pide validar flujos con una interfaz en grises.

**Decisión.** Los tokens de color de `desing.md` §3 son la base; la marca definitiva queda fuera de alcance hasta validar los flujos.

**Consecuencias.** Menos decisiones bloqueantes al inicio. Introduce un paso de restyling posterior, acotado si se usan tokens.

---

## ADR-008 — El nivel se muestra como dato, no como selector

**Estado:** aceptada · **Fecha:** 2026-10-22 · **Resuelve:** `open-questions.md` Q1

**Contexto.** El wireframe muestra tres chips de nivel por idioma (`A1 B1 B2`) con uno resaltado, lo que se lee como un selector. `desing.md` §4 aclara que son la progresión del usuario, no tres niveles elegidos a la vez, y §8 exige que cambiar de nivel sea una acción explícita de configuración o evaluación, «no un simple filtro cualquiera».

**Decisión.** En el sidebar, el idioma muestra **un solo badge** con su nivel actual, no interactivo. El nivel se cambia únicamente en la vista de idioma (`/languages`), con acción explícita y confirmación.

**Consecuencias.** La implementación se aparta del wireframe en ese detalle, por indicación del humano. Cambiar de nivel actualiza el contexto de chat, lecciones, planes y progreso de ese idioma, sin tocar los demás.

---

## ADR-009 — Los tokens del documento mandan sobre los píxeles del wireframe

**Estado:** aceptada · **Fecha:** 2026-10-22 · **Resuelve:** `open-questions.md` Q2

**Contexto.** Los valores medidos en el wireframe difieren de la tabla de `desing.md` §3 (burbuja del tutor `#EFEFEF` vs `--bg-surface #FAFAFA`; burbuja del usuario `#DCDBDB` vs `--bg-user-message #EDEDED`; ítem activo `#CCCCCC` vs `--bg-hover #ECECEC`).

**Decisión.** La tabla de tokens de `desing.md` §3 es la fuente de los colores. El wireframe es referencia de **estructura, jerarquía y espaciado**, no de valores exactos. Toda la UI toma color de los tokens; ningún componente hardcodea un color medido de la imagen.

**Consecuencias.** El render no va a coincidir píxel a píxel con la imagen de referencia. Si se quisiera esa fidelidad exacta, hay que actualizar §3 de `desing.md` — y eso lo decide el humano.

---

## ADR-010 — React + Vite + TypeScript para el frontend

**Estado:** aceptada · **Fecha:** 2026-10-22 · **Resuelve:** `open-questions.md` Q3

**Contexto.** La PWA necesita routing en cliente, estado de idioma activo y componentes reutilizables descritos en `desing.md` §10. Se evaluaron Vite, Next.js y SvelteKit.

**Decisión.** React 18 + Vite + TypeScript estricto, con CSS propio construido sobre los tokens de `desing.md` §3. Routing con `react-router-dom`. Sin librería de UI ni framework de CSS.

**Consecuencias.** Build rápido y despliegue estático junto a la API. La estructura de `frontend/` de `architecture.md` §2 queda confirmada. Un meta-framework con SSR queda descartado por ahora: no hay requisito de SEO y sí un backend propio.

---

## ADR-011 — Inicio separado de la conversación

**Estado:** aceptada · **Fecha:** 2026-10-22 · **Corrige:** defecto de layout de F1

**Contexto.** En F1 las tres tarjetas de resumen y el hilo vivían en la misma pantalla. `ChatPage` renderizaba
cuatro hijos (tarjetas, aviso, hilo, compositor) dentro de una grilla de **tres** filas: la fila `minmax(0, 1fr)`
caía sobre el aviso, `.chat__scroll` quedaba en fila `auto` y tomaba alto de contenido, y el hilo desbordaba la
grilla y se dibujaba **encima** del aviso y de las tarjetas. Con ventanas bajas el compositor quedaba empujado
fuera del área visible. El humano reportó el síntoma: «la parte del chat aparece encima de unos textos y no se
logra diferenciar».

**Decisión.** Se separan dos rutas con responsabilidades distintas, y se conservan los textos de las tarjetas:

| Ruta | Contenido |
|---|---|
| `/` | Inicio: tarjetas de resumen, aviso de datos de ejemplo e historial del idioma activo |
| `/chat/:conversationId` | Conversación: solo hilo y compositor |
| `/chat` | Redirección a `/` (ruta heredada) |

Regla de layout que acompaña la decisión: **cada bloque del área principal ocupa su propia fila** de la grilla y la
grilla declara columnas `minmax(0, 1fr)` para que ningún ítem crezca más allá del contenedor. El hilo hace scroll
dentro de su propio contenedor y el compositor permanece dentro del viewport. Ningún bloque se posiciona para
dibujarse encima de otro.

**Consecuencias.** `desing.md` §4, §5, §6.1 y §9 describen las dos pantallas. El historial del inicio se filtra por
`language_id` (regla de AGENTS.md §3) y en F2 lo alimenta el backend; hoy usa datos de ejemplo. El sidebar marca
«Conversaciones» como activo también dentro de una conversación. Verificado con una sonda de geometría en Chrome
headless sobre ocho viewports: sin solapamiento y sin contenido fuera del viewport en `/` y `/chat/:id`.

---

## ADR-012 — SQLite, SQLAlchemy 2 + Alembic, `uv` y sin auth en v0

**Estado:** aceptada · **Fecha:** 2026-10-22

**Contexto.** F2 necesita levantar el backend con persistencia real y `docs/stack.md` tenía cinco decisiones
pendientes que bloqueaban el arranque: base de datos, ORM, gestor de paquetes, autenticación y testing.

**Decisión.**

1. **SQLite** como único motor por ahora (`sqlite+aiosqlite:///./polybot.db`); no hay PostgreSQL en desarrollo.
2. **SQLAlchemy 2 en modo asíncrono + Alembic** para el esquema y las migraciones.
3. **`uv`** como gestor de paquetes y entorno, con Python `>=3.12` y `backend/uv.lock` versionado.
4. **Sin autenticación en v0**: la API queda abierta en local y la decisión se retoma antes de exponerla.
5. Testing del backend con **pytest + httpx**, la propuesta registrada en `docs/stack.md`.

**Consecuencias.**

- Un solo motor simplifica el arranque: sin servicio externo ni contenedor. Migrar a PostgreSQL es una decisión
  aparte y queda listada como pendiente en `docs/stack.md`.
- El modelo evita tipos no portables (`JSONB`, `ENUM`, `ARRAY`, UUID nativo) y guarda los ids como UUID v4 en
  `String(36)`: el cambio a PostgreSQL no debería tocar dominio ni contrato.
- La app y Alembic comparten la misma URL asíncrona; las migraciones corren con `asyncio` y `render_as_batch` para
  que SQLite acepte los `ALTER`.
- Sin auth no hay entidad `user`: el «perfil de usuario» del wireframe sigue decorativo y Q5 de
  `docs/open-questions.md` queda resuelta.
- Los tests migran una base temporal con Alembic en lugar de llamar a `create_all`: una migración rota rompe la
  suite.

**Alternativas descartadas.** PostgreSQL + SQLite en desarrollo (dos motores desde el día uno); SQL escrito a mano
sin ORM (migraciones a cargo del equipo); token fijo desde el arranque (suma guard y configuración sin uso real).

---

## ADR-013 — El tutor es una instancia de Pi detrás del puerto `LLM`

**Estado:** aceptada · **Fecha:** 2026-10-23 · **Resuelve:** filas «Motor del tutor» y «Streaming de texto» de `docs/stack.md`

**Contexto.** `docs/stack.md` tenía en **Pendiente** el motor del tutor y el transporte del streaming, y ambas bloqueaban el chat real de F3. Antes de escribir código el humano eligió que el tutor sea «una instancia de pi»: no se agregó un proveedor cloud, ni un SDK, ni una clave nueva.

**Decisión.**

1. El adaptador `LLM` lanza `pi --print --mode json` como subproceso por turno y lee el JSONL de Pi
   (`message_update` con `text_delta`, `message_end` autoritativo, `agent_settled`).
2. La invocación fija `--no-session`, `--no-tools`, `--no-builtin-tools`, `--no-context-files`,
   `--no-extensions`, `--no-skills`, `--no-mcp`, un directorio de trabajo temporal y un timeout propio:
   el tutor es texto, no un agente con acceso al repositorio.
3. El prompt vive versionado en `backend/app/adapters/llm/prompts/` (`tutor.v1`, `feedback.v1`).
4. El chat usa SSE: `POST /conversations/{id}/messages` y `GET /conversations/{id}/stream?message_id=`,
   con eventos `token`, `message_end`, `correction`, `vocabulary` y `error`. WebSocket queda para el intérprete.

**Consecuencias.**

- Cambiar de proveedor o de harness es cambiar un adaptador: `application/` y la UI no se enteran (ADR-004).
- El modelo lo resuelve el Pi instalado; `PI_MODEL` lo fija sin tocar código. La API sigue sin estado: el historial
  viaja en cada turno y el subproceso corre con `--no-session` (`docs/architecture.md` §6).
- Costo de seguridad declarado: el backend ejecuta un binario externo por turno. Se acota con el aislamiento de flags
  y de cwd, y ese riesgo se verifica aparte antes de cerrar la fase.
- La suite usa un doble determinista de `LLM`; el turno real contra Pi se verifica en la verificación de F3, no en CI.

---

## ADR-014 — La traducción es un turno corto del mismo proveedor, y solo el mensaje se guarda

**Estado:** aceptada · **Fecha:** 2026-10-23 · **Resuelve:** `/translate` de `docs/api-contract.md` (estaba
en el contrato sin implementar) y habilita la traducción por selección de `desing.md` §6.1.2 y §8

**Contexto.** `desing.md` §8 ya pedía «Pulsar «Traducir» → mostrar la traducción de ese mensaje», y el
contrato listaba `/translate` sin implementación: la pantalla tenía el botón con un texto fijo. El pedido
del humano (`odd/tasks/message-translation.md`, L1) agregó la traducción de un fragmento seleccionado, y
en L2 eligió que el disparo sea el botón del mensaje, sin UI flotante.

**Decisión.**

1. Un tercer uso del mismo proveedor: `LlmPort.translate(TranslationRequest)`, con el prompt versionado
   `translate.v1` y la misma invocación aislada que el tutor y el cierre del turno (ADR-013). Sin SDK, sin
   clave y sin proveedor nuevo.
2. Dos endpoints con dos vidas distintas: `POST /translate` traduce sin guardar (el fragmento) y
   `POST /conversations/{id}/messages/{message_id}/translation` traduce y persiste el mensaje completo. El
   segundo es idempotente: con traducción guardada no se vuelve a llamar al proveedor.
3. La dirección la decide el servidor desde el `LanguageProfile` de la conversación —origen `code`,
   destino `explanation_language`— y nunca desde el idioma activo global (AGENTS.md §3).
4. Solo el mensaje completo se persiste, en `messages.translation`, columna que ya existía: el fragmento
   vive en el estado de la burbuja y se pierde al recargar a propósito.
5. Una respuesta vacía o desmesurada es `llm_unavailable` (502), nunca una traducción vacía guardada.

**Consecuencias.**

- Cada traducción cuesta una invocación del proveedor, arranque incluido: la primera puede tardar
  segundos. La burbuja muestra «Traduciendo…» y el resto del chat sigue usable.
- Cambiar el comportamiento de la traducción es cambiar un archivo versionado (`translate.v1`), no código.
- La suite cubre el adaptador con el subproceso simulado y la API con el doble de `LLM`; la traducción real
  contra Pi se verifica a mano, como en F3.

---

## Precedencia entre el documento y el wireframe

Si el texto de `desing.md` y la imagen `grayscale_language_tutor_chat_ui.png` difieren: **manda el texto**.
La imagen aporta composición y proporciones; las reglas de comportamiento, estados y valores viven en el documento.

