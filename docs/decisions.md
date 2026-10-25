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

## ADR-015 — Whisper no: **Whistle** local como STT de F4

**Estado:** aceptada · **Fecha:** 2026-10-23 · **Resuelve:** Q4 de `docs/open-questions.md` y la fila
«Audio → texto (STT)» de `docs/stack.md`, que bloqueaban F4

**Contexto.** F4 estaba bloqueada porque Q4 pedía el nombre exacto del modelo, si corre local o en
servidor, si soporta streaming y qué idiomas cubre. El humano confirmó el modelo y su fuente:
`https://huggingface.co/Cactus-Compute/whistle`.

**Decisión.**

1. STT = **Whistle** (Cactus Compute), en el backend, local y por CPU, a través del paquete `cactus-needle`
   (existe en PyPI, 3.2.8, Python ≥ 3.9). Sin GPU, sin proveedor cloud y sin clave nueva. Verificado en
   esta máquina: 0,41 s por 3 s de audio con el motor caliente, 8,7 s la primera llamada.
2. El adaptador fija **`NEEDLE_TELEMETRY=0`** antes de importar el paquete: `cactus-needle` recolecta
   conteos de uso anónimos (función, versión, SO) por defecto. No manda audio ni transcripciones, pero
   «local» tiene que ser cierto también para el contador.
3. Detrás de un puerto `STT` con adaptador reemplazable, igual que `LLM` (ADR-004): la UI habla con la API,
   no con un modelo.
4. Streaming nativo del motor (`needle_stream_transcribe_*`) para el intérprete; una pasada acotada para el
   micrófono de una frase.
5. Idiomas cubiertos por el modelo: inglés, alemán, francés, español, italiano, neerlandés y polaco. La
   detección es automática salvo que se fuerce el idioma.

**Consecuencias.**

- El audio no sale de la máquina. Sigue sin prometerse conversación offline (ADR-006): el modelo corre en el
  servidor, no en el navegador.
- Los siete idiomas acotan qué se puede practicar con voz en v0; un idioma fuera de esa lista necesita otro
  adaptador antes de prometer voz.
- `cactus-needle` es una dependencia nueva de `backend/` y entra por esta decisión, no por iniciativa de un
  agente. La primera tarea de F4 es verificarla de verdad en esta máquina: instalar, transcribir un clip
  real y medir latencia. Si no corre acá, la decisión vuelve al humano con la evidencia.

---

## ADR-016 — Piper por binario y subproceso, no por el paquete de Python

**Estado:** aceptada · **Fecha:** 2026-10-23 · **Ajusta:** la parte de implementación de ADR-003

**Contexto.** ADR-003 decidió Piper como TTS local. La implementación natural era el paquete
`piper-tts` de PyPI, pero arrastra `onnxruntime`, `numpy` y seis dependencias transitivas (~45 MB), y
la descarga desde `files.pythonhosted.org` se corta desde esta máquina. El binario oficial de Piper
(`piper_linux_x86_64.tar.gz`, 26,5 MB) trae `libonnxruntime` y `libespeak-ng` adentro.

**Decisión.**

1. Piper se usa como **binario por subproceso**, igual que Pi para el tutor (ADR-013): el adaptador
   lanza `piper --model <voz.onnx> --output_file <wav> --length_scale <escala>` y le pasa el texto
   por `stdin`.
2. El binario y las voces viven fuera del repositorio, en `data/` (ignorado): `data/piper-bin/` y
   `data/piper-voices/`. Las rutas son configuración (`PIPER_BIN_PATH`, `PIPER_VOICES_DIR`,
   `PIPER_SPEECH_DIR`).
3. Cada idioma tiene una voz por defecto por nombre de archivo; una voz que falta es
   `voice_not_available` (400), no un fallo del motor.
4. La síntesis es **síncrona y cacheada por contenido** (`sha256(texto|voz|velocidad)`): la segunda
   petición del mismo texto no vuelve a sintetizar y `GET /voice/speech/{id}` la sirve del disco.
5. La salida es WAV mono 16 bits a 22,05 kHz, el formato nativo del modelo.

**Consecuencias.**

- No se agrega ninguna dependencia Python para el TTS: el backend sigue con `cactus-needle` y
  `python-multipart`.
- Verificado en esta máquina: 1,9 s de audio en 0,31 s de reloj (RTF ≈ 0,05), español y francés, con
  las voces `es_ES-davefx-medium` y `fr_FR-siwis-medium`.
- Las voces por defecto son las `high` cuando existen (`de_DE-thorsten-high`, `en_US-lessac-high`,
  `es_MX-claude-high`); cuestan ~6× más inferencia que las `medium` en alemán e inglés y siguen muy
  por debajo del tiempo real. El francés no tiene `high` y queda en `medium`.
- La instalación del binario es un paso documentado, no automático: sin él, el endpoint responde
  `tts_unavailable` con un mensaje accionable y el resto de la app funciona igual.
- El "streaming por frases" de ADR-003 queda como un proceso por frase, encadenado en el adaptador.

---

## ADR-017 — Las lecciones son catálogo sembrado y la corrección es determinista

**Estado:** aceptada · **Fecha:** 2026-10-23 · **Decide:** F5, tareas T1–T2

**Contexto.** `desing.md` §6.2 pide catálogo de unidades, práctica interactiva y feedback del
tutor; §13 deja la *generación* de lecciones para después de la base. Un catálogo generado por el
modelo no es estable entre idiomas ni testeable: el mismo pedido devuelve otro contenido, y sin
contenido fijo no hay corrección que se pueda afirmar.

**Decisión.**

1. La v0 sirve un **catálogo de datos sembrados por idioma** (`app/adapters/db/lesson_content.py`
   más el seed idempotente): unidades, lecciones, ejercicios, respuestas aceptadas y vocabulario.
   Un idioma sin catálogo muestra el estado vacío con su motivo, nunca una lección inventada.
2. La práctica de v0 es **producir texto en el idioma practicado**, corregido de forma
   **determinista**: se comparan las respuestas sin mayúsculas, sin acentos y sin puntuación. El
   primer idioma aceptado de cada ejercicio es el que se muestra como respuesta esperada.
3. El proveedor del tutor escribe **solo el comentario de cierre**, en el idioma de explicación del
   perfil, y es **best-effort**: si falla, la lección se corrige igual y el comentario queda `null`.
4. Cada intento se persiste con sus respuestas (`lesson_attempts`, `lesson_attempt_answers`) aunque
   `GET /progress` sea F6: el estado de cada sesión y el progreso futuro se derivan de intentos
   reales, no de un contador inventado por la UI.
5. El estado de una lección se **deriva**: `pending` sin intentos, `in_progress` con un intento que
   dejó algo mal, `completed` con un intento sin errores. Ningún endpoint cambia ese estado a mano.

**Consecuencias.**

- Agregar lecciones es editar datos y volver a sembrar, no tocar código.
- La corrección no depende de la latencia ni del criterio del modelo: la suite la cubre sin red.
- Ampliar la práctica a otros tipos de ejercicio (elección múltiple, audio) es una decisión nueva:
  este ADR fija el tipo de la v0, no el definitivo.
- El contenido sembrado es de ejemplo y está marcado como tal: no es currículo validado por un
  docente.

## Precedencia entre el documento y el wireframe

Si el texto de `desing.md` y la imagen `grayscale_language_tutor_chat_ui.png` difieren: **manda el texto**.
La imagen aporta composición y proporciones; las reglas de comportamiento, estados y valores viven en el documento.

