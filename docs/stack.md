# Stack — Polybot

Regla: acá solo se escribe lo que el humano decidió. Lo recomendado pero no confirmado va en **Pendiente**,
con una propuesta explícita. Un agente no promueve una propuesta a decisión por su cuenta.

## Decidido

| Área | Decisión | Notas |
|---|---|---|
| Backend | **FastAPI** (Python) | Prioridad: escalabilidad y API tipada con OpenAPI. |
| Texto → audio (TTS) | **Piper** | Voces por idioma; síntesis local; streaming por frases. |
| Producto | PWA de tutor de idiomas centrada en el chat | Ver `desing.md`. |
| Frontend | **React 18 + Vite + TypeScript**, CSS propio sobre los tokens de `desing.md` §3, `react-router-dom` | Sin librería de UI ni framework de CSS. |
| UI | Español, monocromática minimalista | Wireframe en grises; marca definitiva fuera de alcance. |
| Acoplamiento | Frontend independiente del harness | La UI solo habla HTTP/SSE con la API. |

## Pendiente (con propuesta, sin confirmar)

| Área | Estado | Propuesta | Qué bloquea |
|---|---|---|---|
| Audio → texto (STT) | Pendiente de validar | Modelo mencionado por el usuario como **"Cactus Whistle"**: hay que confirmar nombre exacto, si corre local o en servidor, streaming y cobertura de idiomas | Fase de voz. |
| Base de datos | Pendiente | PostgreSQL; SQLite solo para desarrollo local | Modelo de datos y migraciones. |
| ORM / migraciones | Pendiente | SQLAlchemy 2 + Alembic | Bloqueado por la base. |
| Motor del tutor | Pendiente | Contrato propio `LLM` con un proveedor inicial; prompt del tutor versionado en el repo | Chat real. |
| Streaming de texto | Pendiente | SSE para respuestas del tutor; WebSocket solo para intérprete | Chat real. |
| Autenticación | Pendiente | Sin auth en v0 (uso local); decidir antes de exponer la API | Despliegue. |
| Despliegue | Pendiente | Contenedor único (API + Piper) + estáticos de la PWA | Nada por ahora. |
| Gestor de paquetes Python | Pendiente | `uv` | Arranque del backend. |
| Testing backend | Pendiente | `pytest` + `httpx` | Arranque del backend. |
| Testing frontend | Pendiente | `vitest` + Testing Library; Playwright para flujos | Arranque del frontend. |
| Gestor de paquetes JS | Decidido: `npm` | — | — |

## Convenciones de entorno

- Python objetivo: 3.12 o superior (confirmar al crear el esqueleto).
- Node: LTS vigente al momento de crear `frontend/`.
- Secretos y configuración por `.env` en la raíz; plantilla en `docs/env.example` (`cp docs/env.example .env`). El `.env` real nunca entra al repositorio.

## Cómo se actualiza este archivo

1. El humano confirma una decisión.
2. Se mueve la fila de **Pendiente** a **Decidido** con la fecha.
3. Se agrega la entrada correspondiente en `docs/decisions.md`.
4. Si la decisión cambia el contrato, se actualiza `docs/api-contract.md` en el mismo commit.
