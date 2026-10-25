# Contrato API v0 — Polybot

Estado: **borrador**. Es el acuerdo entre `frontend/` y `backend/`; si cambia, se actualiza acá en el mismo commit.
Prefijo: `/api/v1`. Formato: JSON UTF-8. Fechas: ISO 8601 UTC (`2026-10-22T14:03:00Z`).

## 1. Convenciones

- Nombres de campos en `snake_case` (coincide con Python; el frontend adapta en su capa de tipos).
- Identificadores: UUID v4 como string.
- Paginación por cursor: `?limit=20&cursor=<opaco>`; respuesta `{ "items": [...], "next_cursor": "..." | null }`.
- Errores: siempre el sobre del punto 4, nunca HTML ni texto plano.
- Códigos de error estables (el `code` no se traduce; el `message`, sí): `language_not_found`, `conversation_not_found`, `message_not_found`, `invalid_turn_message`, `language_already_exists`, `active_language_cannot_be_archived`, `last_language_cannot_be_archived`, `plan_not_found`, `plan_already_exists`, `invalid_cursor`, `validation_error`, `not_found`, `method_not_allowed`, `llm_unavailable`, `llm_timeout`, `lesson_not_found`, `missing_lesson_answers`, `invalid_audio`, `audio_too_long`, `stt_unavailable`, `internal_error`. Un código nuevo se agrega acá en el mismo commit que lo introduce.
- Operaciones de escritura aceptan `Idempotency-Key` (header) cuando el reintento duplicaría un turno.
- Zona horaria: el cliente envía `tz` cuando el cálculo lo requiera (metas semanales); el servidor guarda UTC.

## 2. Tipos base

```jsonc
// LanguageProfile
{ "id": "uuid", "code": "fr", "name": "Francés", "level": "A1",
  "explanation_language": "es", "is_active": true, "archived": false,
  "weekly_goal": { "conversations": 7, "minutes": 90 }, "created_at": "..." }

// Conversation
{ "id": "uuid", "language_id": "uuid", "mode": "free|guided|roleplay|exercise|live_voice",
  "title": "Pedir un café", "message_count": 12, "last_message_at": "...", "created_at": "..." }

// Message
{ "id": "uuid", "conversation_id": "uuid", "author": "tutor|user",
  "content": "Bonjour ! Comment ça va ?", "translation": null,
  "audio_url": "/api/v1/voice/speech/abc.mp3", "status": "sent|streaming|error",
  "feedback": { "corrections": [ { "original": "...", "corrected": "...", "explanation": "..." } ],
                "vocabulary": [ { "term": "...", "translation": "...", "note": "..." } ] },
  "created_at": "..." }

// Lesson / StudyPlan / Progress: ver desing.md §12. Se definen al implementar cada fase.
```

`feedback` es el cierre del turno del mensaje. **F3.**

- Solo los mensajes del usuario llevan `feedback`; en los del tutor siempre es `null`.
- En un mensaje del usuario es `null` cuando todavía no se cerró su turno, cuando el cierre falló
  o cuando no había nada que corregir ni vocabulario nuevo que sugerir.
- `corrections` viene ordenado y tiene como máximo 5 elementos; `vocabulary`, como máximo 8. Los
  ítems incompletos se descartan, nunca llegan vacíos.
- `note` puede ser `null` (término sin aclaración).

## 3. Endpoints v0

### Sistema
| Método | Ruta | Qué hace |
|---|---|---|
| GET | `/health` | Liveness: `{ "status": "ok", "version": "..." }` |

### Idiomas
| Método | Ruta | Qué hace |
|---|---|---|
| GET | `/languages` | Lista los idiomas no archivados, del más viejo al más nuevo. Responde un **array** JSON, sin paginar: son pocos y la UI los necesita completos. |
| POST | `/languages` | Agrega un idioma (`code`, `name`, `level`, `explanation_language`, `weekly_goal`). Responde 201; el idioma nuevo queda **inactivo**. El `code` se guarda en minúsculas y es único: uno repetido es 409 `language_already_exists`. |
| PATCH | `/languages/{id}` | Cambia `level`, `weekly_goal` o `is_active`. Activar uno desactiva el anterior. |
| DELETE | `/languages/{id}` | Archiva (blando) y responde 204. Archivar el idioma activo es 409 `active_language_cannot_be_archived`: la UI debe activar otro primero. |

### Conversaciones y mensajes
| Método | Ruta | Qué hace |
|---|---|---|
| GET | `/conversations?language_id=&limit=&cursor=` | Historial del idioma, por última actividad (último mensaje o, si no hay, la creación). `language_id` es obligatorio; un idioma inexistente es 404 `language_not_found`. |
| POST | `/conversations` | Crea conversación (`language_id`, `mode`, `title?`) y responde 201. Sin `title`, el servidor pone `Nueva conversación`. |
| GET | `/conversations/{id}?language_id=&messages_limit=&messages_cursor=` | Conversación con `messages: { items, next_cursor }`; cada mensaje del usuario trae su `feedback` (`null` si no tiene). `language_id` es opcional y sirve de guarda: si la conversación pertenece a otro idioma, responde 404 `conversation_not_found`. |
| PATCH | `/conversations/{id}` | Renombra (`title`). |
| DELETE | `/conversations/{id}` | Elimina con confirmación previa en la UI; borra sus mensajes. Responde 204. |
| POST | `/conversations/{id}/messages` | Envía un mensaje del usuario y devuelve el mensaje persistido (201). `content` de 1 a 4000 caracteres, se guarda sin espacios en los extremos. Acepta `Idempotency-Key`: un reintento con la misma clave en la misma conversación devuelve el mismo mensaje y **no** duplica el turno; sin clave, dos envíos iguales son dos turnos. Conversación inexistente → 404 `conversation_not_found`. |
| GET | `/conversations/{id}/stream?message_id=` | SSE del turno del tutor (ver abajo). `message_id` es el mensaje del usuario que abre el turno: si no existe o es de otra conversación, 404 `message_not_found`; si no es del usuario, 400 `invalid_turn_message`; conversación inexistente, 404 `conversation_not_found`. **F3.** |
| POST | `/conversations/{id}/messages/{message_id}/translation` | Traduce y **guarda** la traducción del mensaje completo, y responde el mensaje (200, mismo `Message` que el detalle). Idempotente: si el mensaje ya tiene `translation`, la devuelve sin llamar al proveedor. Origen y destino salen del perfil del idioma de la conversación. Mensaje de otra conversación → 404 `message_not_found`; conversación inexistente → 404 `conversation_not_found`. Fallo del proveedor → 502 `llm_unavailable` o 504 `llm_timeout`. **ADR-014.** |

#### El stream del turno

`Content-Type: text/event-stream`, `Cache-Control: no-cache`, `X-Accel-Buffering: no`. Cada evento es
`event: <nombre>` + `data: <json>` y termina en una línea en blanco. El servidor cierra el stream al
terminar y, si el cliente corta, corta la llamada al proveedor y guarda lo ya emitido como `error`.

```text
event: token
data: {"message_id": "<id del mensaje del tutor>", "delta": "Bonjour"}

event: message_end
data: { ...Message del tutor, ya persistido con status "sent"... }

event: error
data: {"error": {"code": "llm_unavailable", "message": "...", "details": {}, "request_id": "..."}}
```

Al abrir el turno el mensaje del tutor se guarda con `content: ""` y `status: "streaming"`; `token`
llega mientras se escribe, `message_end` llega **después** del commit que lo deja `sent`, y un corte o
un fallo del proveedor lo deja `error` con el texto parcial, sin `message_end`: el `error` usa el sobre
del punto 4 (`llm_unavailable` 502, `llm_timeout` 504).

Al cerrar el turno llegan, **después** de `message_end`, las correcciones y el vocabulario del mensaje
del usuario que abrió el turno. **F3.**

```text
event: correction
data: {"message_id": "<id del mensaje del USUARIO>",
       "items": [{"original": "...", "corrected": "...", "explanation": "..."}]}

event: vocabulary
data: {"message_id": "<id del mensaje del USUARIO>",
       "items": [{"term": "...", "translation": "...", "note": "..." | null}]}
```

- Ambos eventos llevan el `message_id` del mensaje del **usuario**, no el del tutor: son la
devolución de lo que escribió el estudiante.
- `correction` va antes que `vocabulary`. Si una lista quedó vacía, su evento no se emite; un turno
sin nada que reportar cierra con `message_end` y nada más.
- El cierre es una segunda invocación corta del proveedor: si falla o no devuelve algo parseable, el
chat no se rompe. `message_end` ya se emitió, el mensaje del tutor queda `sent` y los eventos de
feedback simplemente no llegan (el mensaje del usuario conserva `feedback: null`).
- El vocabulario se guarda con el `language_id` de la conversación, no con el idioma activo global.
- Un reintento del stream con el mismo `message_id` reemplaza el feedback de ese mensaje: no se
duplica.

### Feedback en el detalle

`GET /conversations/{id}` adjunta `feedback` a cada mensaje del usuario de la página, con una sola
consulta por página. Así las tarjetas del turno sobreviven a una recarga, porque el dato está en la
base y no solo en el stream.

### Voz
| Método | Ruta | Qué hace |
|---|---|---|
| POST | `/voice/transcribe` | `multipart/form-data` (`audio`, `language_code?`). Devuelve `{ "text", "language_detected", "duration_ms" }`. **F4.** Detalle abajo. |
| POST | `/voice/speech` | Sintetiza y **cachea por contenido**: `{ "text", "language_code", "voice?", "speed?": 1.0 }` → `200 audio/wav` con la cabecera `X-Speech-Id` (sha256 de voz, velocidad y texto). Repetir la misma petición devuelve el mismo id sin volver a sintetizar. Texto de 1 a 2000 caracteres; `speed` de 0,5 a 2,0 → fuera de rango, 422 `validation_error`. Idioma sin voz instalada o voz inexistente → 400 `voice_not_available`; motor caído o sin binario → 502 `tts_unavailable`. **F4, ADR-016.** |
| GET | `/voice/speech/{id}` | Devuelve el WAV cacheado de ese id (`audio/wav`), o 404 `speech_not_found` si ya no está. |
| WS | `/voice/interpret` | Intérprete: envía segmentos de audio, recibe `transcript` y `translation` por turno. |

#### La transcripción

- `audio` es un WAV de **16 kHz, mono, 16 bits**, que es lo que graba el navegador. Otro sample
  rate, más de un canal u otro ancho de muestra → 400 `invalid_audio`: el servidor no remuestrea.
  Un archivo corrupto o que no es un WAV también es 400 `invalid_audio`; un `audio` vacío o
  ausente es 422 `validation_error`.
- `language_code` es opcional. Sin él el motor detecta el idioma; con él la transcripción se fuerza
  a ese idioma (`fr`, también `fr-FR`: se usa el subtag principal). En ambos casos
  `language_detected` es el idioma que informó el motor, o `null` si no lo informó: el servidor no
  inventa un código.
- `duration_ms` sale de los frames del WAV: es la duración del clip, no la del request.
- Un clip **sin voz** devuelve `text: ""` con 200. Es una respuesta válida, no un error: la UI
  tiene que poder decir que no se escuchó nada en vez de inventar una frase.
- Más de **120 s** → 413 `audio_too_long`. Motor caído, error del motor o respuesta ilegible → 502
  `stt_unavailable`. El motor corre en el backend y **el audio no sale de la máquina**.
- El audio **no se guarda** ni temporalmente: se transcribe y se descarta con el request (F4 S7).

#### La síntesis

- La salida es **WAV mono 16 bits a 22,05 kHz**, el formato nativo de las voces de Piper. El
  navegador reproduce cualquier sample rate, así que no se remuestrea.
- `voice` es opcional: sin él se usa la voz por defecto del idioma. Un idioma sin voz instalada es
  400 `voice_not_available` con un mensaje accionable, no un fallo del motor.
- El **caché es por contenido** y vive en el servidor: `GET /voice/speech/{id}` sirve lo ya
  sintetizado. Lo único que se guarda es el audio generado a partir de un texto, nunca una
  grabación del usuario.
- `speed` se traduce a la escala de longitud de Piper (`1 / speed`), así que 0,5 es la mitad de
  rápido.

### Aprendizaje
| Método | Ruta | Qué hace |
|---|---|---|
| GET | `/lessons?language_id=` | Catálogo y próxima lección. |
| GET | `/lessons/{id}` | Lección con ejercicios. |
| POST | `/lessons/{id}/submit` | Resultado, errores y vocabulario nuevo. |
| GET | `/plans?language_id=` | Plan del idioma con su cronograma: `{ "language_id", "plan" }`. Un idioma **sin** plan devuelve `plan: null`, no un error; un idioma inexistente es 404 `language_not_found`. El `status` de cada sesión es **derivado** de los intentos reales de su lección y nunca se guarda: `completed` si hubo un intento con todas las respuestas bien, `in_progress` si hubo un intento con algo mal, `pending` si no hay intento. `weeks` es la cantidad de semanas del cronograma (0 cuando el idioma no tiene lecciones) y `next_session` es la primera sesión que no está `completed`, en orden del cronograma, o `null` si no queda ninguna: es lo que abre «Continuar plan». **F5.** |
| POST | `/plans` | Crea el plan del idioma (`language_id`, `goal`, `frequency`, `daily_minutes`) y responde 201 con el plan. `goal` de 1 a 200 caracteres, recortado; `frequency` de 1 a 7 sesiones por semana; `daily_minutes` de 5 a 120; fuera de rango → 422 `validation_error`. El cronograma se genera del catálogo y es **determinista**: una sesión por lección en orden de catálogo, `frequency` por semana (`week` = índice // `frequency` + 1, `position` = índice % `frequency`). Un plan por idioma: si el idioma ya tiene uno, 409 `plan_already_exists` y nada cambia. Idioma inexistente → 404 `language_not_found`. **F5 S3.** |
| PATCH | `/plans/{id}` | Ajusta `frequency` y/o `daily_minutes` (mismos límites que el `POST`) y responde el plan. El `goal` **no** se ajusta: es lo que el usuario pidió al crear el plan. Recalcula el cronograma con la frecuencia nueva y marca `adjusted_at`; un cuerpo vacío no cambia nada, y **nada** recalcula el plan salvo este pedido: no hay job de fondo ni recálculo en el `GET`. Plan inexistente → 404 `plan_not_found`. **F5 S4.** |
| GET | `/progress?language_id=` | Resumen de progreso y errores frecuentes. |
| POST | `/translate` | Traducción **sin estado**: `{ "text", "source?", "target" }` → `{ "translation", "detected_source" }`. Es el camino del fragmento seleccionado: no guarda nada. `source` es el código del idioma de origen; sin `source`, el proveedor lo detecta y `detected_source` vuelve `null` (el servidor no inventa un código que no detectó). `text` de 1 a 4000 caracteres, recortado. Target inválido o texto vacío → 422 `validation_error`. **ADR-014.** |

#### El plan y su cronograma

```jsonc
// Plan
{ "id": "uuid", "language_id": "uuid", "goal": "Pasar de A1 a B1 en francés",
  "frequency": 2, "daily_minutes": 20, "weeks": 4,
  "created_at": "...", "adjusted_at": null,        // null hasta el primer PATCH
  "next_session": PlanSession | null,               // null cuando todas están completas
  "sessions": [ PlanSession ] }

// PlanSession
{ "id": "uuid", "week": 1, "position": 0, "lesson_id": "uuid",
  "lesson_title": "Pedir algo en un café", "status": "pending|in_progress|completed" }
```

- `sessions` viene en orden de cronograma: por `week`, después por `position`.
- El calendario son las semanas de `sessions`: el servidor guarda el cronograma relativo por
  semanas, no fechas. Ponerle días al calendario es tarea de la PWA.
- `status` es de solo lectura en todo el contrato: no hay endpoint que lo cambie a mano.

## 4. Sobre de error

```json
{ "error": { "code": "audio_too_long", "message": "El audio supera los 120 segundos.",
             "details": { "max_seconds": 120 }, "request_id": "..." } }
```

| HTTP | Cuándo |
|---|---|
| 400 | Entrada inválida, audio corrupto o formato de audio no soportado. |
| 401 / 403 | Falta autorización o permiso (cuando exista auth). |
| 404 | Recurso inexistente o ajeno al idioma activo. |
| 409 | Conflicto de estado (p. ej. activar idioma archivado). |
| 413 | Audio o payload por encima del límite. |
| 422 | Error de validación de esquema (FastAPI). |
| 429 | Límite de uso por sesión. |
| 502 / 504 | Fallo o timeout de un proveedor (STT, LLM, TTS). |

Mensajes visibles al usuario en español, accionables («Reintentar», «Revisar permisos de micrófono»).
El `code` es estable y no se traduce; el `message` sí.

## 5. Límites v0

| Límite | Valor inicial |
|---|---|
| Audio por request de transcripción | 120 s |
| Formato del audio de transcripción | WAV 16 kHz, mono, 16 bits (sin remuestreo del lado del servidor) |
| Audio por request de síntesis | 2000 caracteres |
| Mensajes por página | 50 |
| Conversaciones por página | 20 (`limit` acepta 1–50) |
| Contenido por mensaje | 4000 caracteres (`content` de 1 a 4000, sin espacios en los extremos) |
| Texto por request de traducción | 4000 caracteres (`text` de 1 a 4000, sin espacios en los extremos) |
| Texto por request de síntesis | 2000 caracteres (`text` de 1 a 2000, sin espacios en los extremos) |
| Velocidad de reproducción | 0,5 a 2,0 (`speed`, 1,0 por defecto) |
| Timeout por proveedor | 30 s (LLM 60 s) |
| Tokens de contexto por turno | A definir con el prompt del tutor |
