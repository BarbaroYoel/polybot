# Contrato API v0 — Polybot

Estado: **borrador**. Es el acuerdo entre `frontend/` y `backend/`; si cambia, se actualiza acá en el mismo commit.
Prefijo: `/api/v1`. Formato: JSON UTF-8. Fechas: ISO 8601 UTC (`2026-10-22T14:03:00Z`).

## 1. Convenciones

- Nombres de campos en `snake_case` (coincide con Python; el frontend adapta en su capa de tipos).
- Identificadores: UUID v4 como string.
- Paginación por cursor: `?limit=20&cursor=<opaco>`; respuesta `{ "items": [...], "next_cursor": "..." | null }`.
- Errores: siempre el sobre del punto 4, nunca HTML ni texto plano.
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
| GET | `/languages` | Lista idiomas no archivados. |
| POST | `/languages` | Agrega un idioma (`code`, `level`, `explanation_language`). |
| PATCH | `/languages/{id}` | Cambia nivel, meta o `is_active`. Activar uno desactiva el anterior. |
| DELETE | `/languages/{id}` | Archiva (blando). Requiere confirmación en la UI. |

### Conversaciones y mensajes
| Método | Ruta | Qué hace |
|---|---|---|
| GET | `/conversations?language_id=&cursor=` | Historial del idioma, más recientes primero. |
| POST | `/conversations` | Crea conversación (`language_id`, `mode`, `title?`). |
| GET | `/conversations/{id}` | Conversación con sus mensajes paginados. |
| PATCH | `/conversations/{id}` | Renombra (`title`). |
| DELETE | `/conversations/{id}` | Elimina con confirmación previa en la UI. |
| POST | `/conversations/{id}/messages` | Envía mensaje del usuario; devuelve el mensaje persistido. |
| GET | `/conversations/{id}/stream?message_id=` | SSE: `token`, `message_end`, `correction`, `error`. |

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
| Timeout por proveedor | 30 s (LLM 60 s) |
| Tokens de contexto por turno | A definir con el prompt del tutor |
