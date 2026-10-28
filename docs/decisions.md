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

## ADR-018 — El progreso se deriva de señales reales, sin métricas inventadas

**Estado:** aceptada · **Fecha:** 2026-10-26 · **Decide:** F6

**Contexto.** `desing.md` §6.5 pide un resumen con «nivel, sesiones completadas, tiempo practicado y
meta semanal», evolución de cinco destrezas y errores frecuentes. Lo persistido hasta F5 solo
registra conversaciones y mensajes con fecha, intentos de lección con sus respuestas, correcciones
del cierre de turno y términos sugeridos. No hay duración de sesiones, ni eventos de lectura, ni
registro de reproducción de audio. La fecha del nivel también es un dato del perfil, no una medición.

**Decisión.**

1. **Sin minutos en v0.** No se estima ni se inventa «tiempo practicado»: la pantalla muestra nivel,
   lecciones completadas y meta semanal de conversaciones. Medir duración real es una fase aparte.
2. **Solo tres destrezas con señal real**: conversación (conversaciones con mensajes), escritura
   (respuestas de ejercicios enviadas) y vocabulario (términos sugeridos). Lectura y escucha vuelven
   `available: false` y la UI las muestra como «sin datos todavía», no como un cero medido.
3. **Los errores frecuentes se agrupan, no se generan**: pares exactos de corrección del tutor y de
   respuestas incorrectas de lecciones, ordenados por recurrencia con `language_id`.
4. **El nivel es de solo lectura acá.** Se lee del `LanguageProfile` y se cambia únicamente en
   `/languages` con acción explícita (ADR-008); Progreso no lo calcula, no lo propone y no lo mueve.
5. **Sin esquema nuevo.** `GET /progress` es una vista de lectura sobre tablas existentes: no hay
   migración ni escritura en F6.

**Consecuencias.**

- La pantalla puede decir «todavía no hay datos suficientes» sin mentir; es un estado de éxito, no un
  error.
- Los contadores miden **actividad registrada**, no dominio del idioma. La copia de la UI no debe
  presentarlos como una evaluación de nivel.
- «Vocabulario» cuenta términos sugeridos, no términos demostrados: se rotula como tal.
- Cuando exista medición de duración o de escucha/lectura, se revisa este ADR y se agregan señales;
  no se parchea la UI con estimaciones.

## ADR-019 — OpenCode como adaptador alternativo del puerto `LLM`

**Estado:** aceptada · **Fecha:** 2026-10-26 · **Decide:** cambio de proveedor del tutor pedido por el humano

**Contexto.** El tutor se implementó sobre una instancia de Pi por turno (ADR-013), pero este entorno
no tiene `pi` instalado: el chat y la traducción respondían `llm_unavailable`. OpenCode v2.1.4 sí está
instalado y tiene un servicio en segundo plano con proveedores ya autenticados. La UI y
`application/` no conocen el harness (ADR-004), así que el cambio corresponde a un adaptador.

**Decisión.**

1. Se agrega `OpenCodeCliAdapter` detrás del mismo `LlmPort`; dominio, casos de uso, contrato HTTP y
   PWA no cambian.
2. `LLM_PROVIDER=pi|opencode` elige el adaptador. El default sigue siendo `pi` para no romper
   instalaciones existentes; este Codespace usa `opencode` en su `.env` local.
3. Cada invocación ejecuta `opencode run --format json --agent plan -- <prompt>` en un directorio
   temporal, con timeout y sin sesión persistente. El agente `plan` es de solo lectura y el prompt
   completo viaja como mensaje, porque el CLI no tiene `--system-prompt`.
4. `OPENCODE_MODEL` fija el modelo (`proveedor/modelo`); no se hardcodea ninguno, porque cada
   instalación autoriza proveedores distintos. `OPENCODE_AGENT` y `OPENCODE_TIMEOUT_SECONDS` también
   son configuración.
5. El cierre del turno, la traducción y el comentario de lección reutilizan las mismas reglas de
   validación (`adapters/llm/parsing.py`) que el adaptador Pi: cambiar de proveedor no cambia qué es
   una respuesta usable.

**Consecuencias.**

- El tutor funciona sin Pi cuando OpenCode está instalado y autenticado; cambiar de uno a otro es
  configuración, no código.
- La calidad, latencia y costo dependen del modelo elegido en `OPENCODE_MODEL`. Si el modelo por
  defecto de la instalación no está permitido (como pasó con el modelo Go por privacidad), hay que
  fijarlo explícitamente.
- El streaming llega por partes de texto del CLI, no necesariamente token por token: la UI recibe
  deltas, pero el primer texto puede aparecer más tarde que con Pi.
- `plan` es de solo lectura, pero OpenCode conserva sus herramientas de lectura: el aislamiento se
  apoya en el directorio temporal y en el agente, no en un sandbox del sistema. Acotarlo con un
  agente sin herramientas es una mejora futura.
- Se suma el CLI de OpenCode como requisito del proveedor, no como dependencia Python. La suite lo
  prueba con un fixture JSONL; la llamada real se verifica a mano.

---

## ADR-020 — Bloques de práctica tipados en el turno del tutor

**Estado:** aceptada · **Fecha:** 2026-10-26 · **Decide:** F6.5

**Contexto.** `desing.md` §6.1.2 ya prevé que una respuesta del tutor pueda traer «audio, ejercicios,
traducciones, correcciones o tarjetas de vocabulario», pero hasta F6 solo las correcciones y el
vocabulario eran datos estructurados (`Message.feedback`); el resto del turno era texto plano y el
ejercicio de lección era un único tipo: escribir la frase (ADR-017). La idea de **interfaz
inteligente** —el modelo responde con componentes interactivos en vez de párrafos— viene del
proyecto pixelUI del mismo autor, donde el modelo llama `render_ui` y el cliente valida un árbol de
bloques. Copiar ese mecanismo tal cual choca con ADR-004 y con `desing.md` §12: la UI no puede
acoplarse a un harness.

**Decisión.**

1. Se agregan **bloques de práctica tipados** al mensaje del **tutor**: `phrase` (una frase para
   escuchar) y `drill` (una pregunta con corrección determinista). El árbol es **chato**: 0 a 2
   bloques, como máximo uno interactivo, sin anidar.
2. **El modelo propone contenido, no interfaz.** No hay equivalente a `render_ui`: el modelo no elige
   componente, layout ni jerarquía; llena campos de tipos conocidos. La validación y los límites
   viven en `domain/blocks.py`, no en el prompt.
3. Los bloques viajan en el **cierre de turno** ya existente (`feedback.v2`), no en una tercera
   llamada: la latencia después de `message_end` no se duplica. El parseo es **tolerante por
   sección**: si `blocks` viene mal, se descarta y las correcciones de ese turno se conservan.
4. Se emiten como evento SSE `blocks`, **después** de `message_end` y **antes** de `correction` y
   `vocabulary`, con el `message_id` del tutor. Se guardan con el mensaje (`messages.blocks_json`) y
   `GET /conversations/{id}` los devuelve, así sobreviven a una recarga.
5. Las **respuestas aceptadas de un drill nunca viajan al cliente** antes de responder. La respuesta
   se corrige en `POST .../blocks/{block_id}/answers` con `domain/grading.py`, las mismas reglas que
   una lección (ADR-017). `expected` solo se revela tras un fallo.
6. El resultado del drill **no se persiste** en v0: es corrección sin estado, como el fragmento
   traducido (ADR-014). Guardar intentos obligaría a decidir si son señal de `/progress` y a revisar
   ADR-018, y esa no es esta fase.
7. **Nada de gráficos, tablas ni métricas** en el chat: un tutor no es un dashboard, y ADR-018
   prohíbe inventar mediciones.
8. La PWA dibuja los `kind` conocidos con un registro de componentes y muestra un aviso discreto
   ante un `kind` desconocido. Un bloque ilegible nunca rompe el hilo.

**Consecuencias.**

- El chat gana práctica real sin dejar de ser un chat: dos tarjetas como máximo y una sola
  interacción abierta.
- El contrato crece de forma aditiva (`Message.blocks`, evento `blocks`, un endpoint nuevo); ningún
  cliente anterior se rompe, porque `blocks` ausente equivale a `[]`.
- `feedback.v1.md` queda en el árbol como la versión que cerraba un turno sin bloques.
- El drill reutiliza la corrección determinista y el audio de F4: no agrega dependencias ni motores.
- La calidad depende de que el modelo devuelva JSON válido con la forma pedida. Si no lo hace, el
  turno se ve como antes (solo texto) y el fallo queda en el log; no hay UI rota.
- Ampliar tipos de bloque o de ejercicio de lección es una decisión nueva: este ADR fija dos bloques
  y un tipo de drill, no una taxonomía definitiva.

---

## ADR-021 — Las lecciones admiten ejercicios de elección, con la misma corrección determinista

**Estado:** aceptada · **Fecha:** 2026-10-26 · **Decide:** F6.6

**Contexto.** ADR-017 fijó la práctica de la v0 en un solo tipo —producir texto en el idioma— y dejó
dicho que ampliar los tipos es una decisión nueva. `desing.md` §6.2 pide «práctica interactiva» y el
chat ya ganó bloques tipados (ADR-020); las lecciones seguían siendo un formulario de textos. El
humano pidió que chat y lecciones compartan la idea de interfaz inteligente.

**Decisión.**

1. `LessonExercise` gana `kind`: `writing` (lo que ya existía) o `choice` (elegir una opción). Es
   aditivo y con default `writing`, así que ninguna fila existente cambia de significado.
2. Un `choice` ofrece entre 2 y 6 opciones, **sin repetir**, y tiene **exactamente una** respuesta
   aceptada que además es una de sus opciones. Es una regla del contenido, no del renderer: el seed
   la cumple y un test la vigila.
3. **La corrección no cambia.** El cliente envía el texto elegido como `answer` y el servidor lo
   compara con `domain/grading.py`, igual que una respuesta escrita. El tipo cambia el control, no
   el criterio: mayúsculas, puntuación y espacios no cuentan; los acentos sí.
4. La API devuelve `kind` y `options`; las respuestas aceptadas siguen sin viajar al cliente, y la
   opción correcta no se marca de ninguna forma.
5. La UI usa un **grupo de radios de ancho completo**, no un desplegable: leer las cuatro opciones es
   parte del ejercicio. Componentes y tokens existentes; sin dependencias nuevas.
6. El catálogo sembrado suma un `choice` por idioma dentro de una lección existente.

**Consecuencias.**

- Las lecciones se parecen al chat en la forma de practicar sin duplicar el motor de corrección: es
  la misma función determinista para un drill del chat y para un ejercicio de lección.
- El contrato crece de forma aditiva (`kind`, `options`); un cliente viejo que ignore los campos
  sigue funcionando.
- `order` (armar la oración) y `listen` (audio) quedan como decisiones aparte: este ADR fija dos
  tipos, no una taxonomía cerrada.
- El seed no refresca un catálogo ya sembrado (`_seed_lessons` salta los idiomas con unidades), así
  que ver el contenido nuevo exige recrear la base local. Queda anotado como límite; no se cambió el
  seed en esta fase.

---

## ADR-022 — El intérprete reinicia Whistle en ventanas de 4,5 s

**Estado:** aceptada · **Fecha:** 2026-10-28 · **Implementa:** F7 y el `WS /voice/interpret` que el
contrato ya reservaba

**Contexto.** ADR-015 eligió `needle.stream` para el intérprete. Antes de escribir el adaptador, T0
midió el motor con un clip humano de 11 s en este Codespace. Un stream continuo no se sostiene: 11 s
de audio tardaron 26 s con chunks de 1 s y 115 s con chunks de 0,25 s; con 22 s el coste subió a 84 s.
El motor tiene un corte alrededor de los 5 s: `transcribe` de una ventana de 5 s tarda 0,3–1,3 s, pero
una de 5,5 s salta a ~5,8 s. Reiniciar el stream en cada ventana devuelve el coste a 0,3–1,3 s por
ventana. La máquina tiene 2 vCPU y durante la medición otro proceso mantuvo la carga alta, así que
los valores absolutos varían; la discontinuidad de ~5 s se repitió en todas las corridas.

**Decisión.**

1. El intérprete alimenta Whistle en **ventanas de 4,5 s como máximo**; cada ventana abre un
   `needle.stream` nuevo y lo cierra al terminar. No hay un stream continuo de toda la sesión.
2. Cada ventana lleva **0,5 s de solape** con la anterior; el texto del borde se deduplica por
   prefijo/sufijo antes de emitir el segmento. El servidor decide el corte; el cliente solo envía
   audio.
3. Los parciales se emiten por chunk (~1 s) dentro de la ventana. Al cerrarla se emite un `segment`
   con el texto consolidado y su `translation` final. La traducción de parciales sigue P5, con
   *debounce*, una petición en vuelo y descarte por `seq`.
4. Las sesiones son efímeras (P2), el modo texto entra en F7 (P1), la detección de origen es
   opcional (P3) y el TTS queda fuera (P4).
5. El contrato del WebSocket se documenta en `docs/api-contract.md`; los eventos `partial`,
   `partial_translation`, `segment`, `translation` y `error` usan el sobre de error del §4.

**Consecuencias.**

- El intérprete corta cada 4,5 s: puede partir una frase y el texto del borde depende de la
  deduplicación. Es un límite visible, no un fallo silencioso; la UI muestra segmentos, no frases
  perfectas.
- La latencia ya no crece con la duración de la sesión, pero depende de la CPU: si la máquina no da
  abasto, la sesión se atrasa. La UI muestra «Procesando…» y el servidor no promete tiempo real fijo.
- El motor se llama una vez por ventana y el proveedor de traducción recibe parciales; el *debounce*
  y el descarte por `seq` son parte de la corrección, no una optimización opcional.
- La traducción con OpenCode usa **`OPENCODE_TRANSLATION_AGENT`** (default `general`). Con `plan`, el
  modelo narraba su rol y devolvía comentarios meta; la prueba real de T6 lo mostró y el cambio lo
  corrigió. El tutor conserva `plan`. Con el proveedor actual una traducción tarda 3–7 s, así que el
  parcial suele quedar viejo y la UI termina mostrando la traducción del segmento final.
- El corte de 4,5 s puede degradar un segmento corto (una sílaba o una frase partida); el solape de
  0,5 s reduce el borde, no lo elimina. Es un límite visible, no un fallo silencioso.
- Si en el futuro se cambia de motor o se encuentra una forma de mantener el contexto sin el corte de
  5 s, esta decisión se revisa; Whistle no es el único adaptador posible.
- No hay persistencia ni audio guardado: el historial se pierde al recargar (P2).

---

## Precedencia entre el documento y el wireframe

Si el texto de `desing.md` y la imagen `grayscale_language_tutor_chat_ui.png` difieren: **manda el texto**.
La imagen aporta composición y proporciones; las reglas de comportamiento, estados y valores viven en el documento.

