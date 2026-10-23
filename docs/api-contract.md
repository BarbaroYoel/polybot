# Contrato API v0 — Polybot

Estado: **borrador**. Es el acuerdo entre `frontend/` y `backend/`; si cambia, se actualiza acá en el mismo commit.
Prefijo: `/api/v1`. Formato: JSON UTF-8. Fechas: ISO 8601 UTC (`2026-10-22T14:03:00Z`).

## 1. Convenciones

- Nombres de campos en `snake_case` (coincide con Python; el frontend adapta en su capa de tipos).
- Identificadores: UUID v4 como string.
- Paginación por cursor: `?limit=20&cursor=<opaco>`; respuesta `{ "items": [...], "next_cursor": "..." | null }`.
- Errores: siempre el sobre del punto 4, nunca HTML ni texto plano.
- Códigos de error estables (el `code` no se traduce; el `message`, sí): `language_not_found`, `conversation_not_found`, `message_not_found`, `invalid_turn_message`, `language_already_exists`, `active_language_cannot_be_archived`, `last_language_cannot_be_archived`, `invalid_cursor`, `validation_error`, `not_found`, `method_not_allowed`, `llm_unavailable`, `llm_timeout`, `internal_error`. Un código nuevo se agrega acá en el mismo commit que lo introduce.
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
  "created_at": "..." }

// Lesson / StudyPlan / Progress: ver desing.md §12. Se definen al implementar cada fase.
```

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
| GET | `/conversations/{id}?language_id=&messages_limit=&messages_cursor=` | Conversación con `messages: { items, next_cursor }`. `language_id` es opcional y sirve de guarda: si la conversación pertenece a otro idioma, responde 404 `conversation_not_found`. |
| PATCH | `/conversations/{id}` | Renombra (`title`). |
| DELETE | `/conversations/{id}` | Elimina con confirmación previa en la UI; borra sus mensajes. Responde 204. |
| POST | `/conversations/{id}/messages` | Envía un mensaje del usuario y devuelve el mensaje persistido (201). `content` de 1 a 4000 caracteres, se guarda sin espacios en los extremos. Acepta `Idempotency-Key`: un reintento con la misma clave en la misma conversación devuelve el mismo mensaje y **no** duplica el turno; sin clave, dos envíos iguales son dos turnos. Conversación inexistente → 404 `conversation_not_found`. |
| GET | `/conversations/{id}/stream?message_id=` | SSE del turno del tutor (ver abajo). `message_id` es el mensaje del usuario que abre el turno: si no existe o es de otra conversación, 404 `message_not_found`; si no es del usuario, 400 `invalid_turn_message`; conversación inexistente, 404 `conversation_not_found`. **F3.** |

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
del punto 4 (`llm_unavailable` 502, `llm_timeout` 504). Los eventos `correction` y `vocabulary`
(correcciones y términos sugeridos del mensaje del usuario) se agregan al cerrar el turno.

### Voz
| Método | Ruta | Qué hace |
|---|---|---|
| POST | `/voice/transcribe` | `multipart/form-data` (`audio`, `language_code?`). Devuelve `{ "text", "language_detected", "duration_ms" }`. |
| POST | `/voice/speech` | `{ "text", "language_code", "voice?", "speed?": 1.0 }` → `audio/mpeg` o `audio/wav`. |
| GET | `/voice/speech/{id}` | Descarga audio ya sintetizado (cache). |
| WS | `/voice/interpret` | Intérprete: envía segmentos de audio, recibe `transcript` y `translation` por turno. |

### Aprendizaje
| Método | Ruta | Qué hace |
|---|---|---|
| GET | `/lessons?language_id=` | Catálogo y próxima lección. |
| GET | `/lessons/{id}` | Lección con ejercicios. |
| POST | `/lessons/{id}/submit` | Resultado, errores y vocabulario nuevo. |
| GET | `/plans?language_id=` | Plan activo e hitos. |
| POST | `/plans` | Crea plan (`goal`, `frequency`, `daily_minutes`). |
| GET | `/progress?language_id=` | Resumen de progreso y errores frecuentes. |
| POST | `/translate` | `{ "text", "source?", "target" }` → `{ "translation", "detected_source" }`. |

## 4. Sobre de error

```json
{ "error": { "code": "audio_too_long", "message": "El audio supera los 120 segundos.",
             "details": { "max_seconds": 120 }, "request_id": "..." } }
```

| HTTP | Cuándo |
|---|---|
| 400 | Entrada inválida o audio vacío/corrupto. |
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
| Audio por request de síntesis | 2000 caracteres |
| Mensajes por página | 50 |
| Conversaciones por página | 20 (`limit` acepta 1–50) |
| Contenido por mensaje | 4000 caracteres (`content` de 1 a 4000, sin espacios en los extremos) |
| Timeout por proveedor | 30 s (LLM 60 s) |
| Tokens de contexto por turno | A definir con el prompt del tutor |
