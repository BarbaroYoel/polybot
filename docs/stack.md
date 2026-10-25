# Stack — Polybot

Regla: acá solo se escribe lo que el humano decidió. Lo recomendado pero no confirmado va en **Pendiente**,
con una propuesta explícita. Un agente no promueve una propuesta a decisión por su cuenta.

## Decidido

| Área | Decisión | Notas |
|---|---|---|
| Backend | **FastAPI** (Python) | Prioridad: escalabilidad y API tipada con OpenAPI. |
| Texto → audio (TTS) | **Piper**, por **binario y subproceso** (2026-10-23) | Voces por idioma en `data/piper-voices`; síntesis local con caché por contenido; sin dependencias Python (ADR-016). |
| Producto | PWA de tutor de idiomas centrada en el chat | Ver `desing.md`. |
| Frontend | **React 18 + Vite + TypeScript**, CSS propio sobre los tokens de `desing.md` §3, `react-router-dom` | Sin librería de UI ni framework de CSS. |
| UI | Español, monocromática minimalista | Wireframe en grises; marca definitiva fuera de alcance. |
| Acoplamiento | Frontend independiente del harness | La UI solo habla HTTP/SSE con la API. |
| Base de datos (2026-10-22) | **SQLite** (`sqlite+aiosqlite`) | Único motor en v0 (ADR-012). PostgreSQL queda como decisión aparte. |
| ORM / migraciones (2026-10-22) | **SQLAlchemy 2 asíncrono + Alembic** | Una sola URL asíncrona para la app y las migraciones. |
| Gestor de paquetes Python (2026-10-22) | **`uv`** | Python `>=3.12`; `backend/uv.lock` versionado. |
| Autenticación (2026-10-22) | **Sin auth en v0** | API abierta en local; se decide antes de exponerla (ADR-012, cierra Q5). |
| Testing backend (2026-10-22) | **pytest + httpx** | `backend/tests/{unit,integration}`; la API se prueba sobre una base migrada. |
| Motor del tutor (2026-10-23) | **Una instancia de Pi por turno**, detrás del puerto `LLM` | `pi --print --mode json` con herramientas y contexto apagados; sin SDK ni claves propias (ADR-013). |
| Streaming de texto (2026-10-23) | **SSE** para el chat; WebSocket solo para el intérprete | Eventos `token`, `message_end`, `correction`, `vocabulary`, `error` (ADR-013). |
| Traducción de mensajes y fragmentos (2026-10-23) | Un turno corto del mismo puerto `LLM` (`translate.v1`) | Solo el mensaje completo se persiste; el fragmento es efímero (ADR-014). |
| Audio → texto (STT) (2026-10-23) | **Whistle** (Cactus Compute), local en el backend vía `cactus-needle` | CPU, streaming, 7 idiomas; detrás de un puerto `STT` (ADR-015). |

## Pendiente (con propuesta, sin confirmar)

| Área | Estado | Propuesta | Qué bloquea |
|---|---|---|---|
| Base de datos de producción | Pendiente | PostgreSQL; la v0 usa SQLite (ADR-012) | Despliegue. |
| Despliegue | Pendiente | Contenedor único (API + Piper) + estáticos de la PWA | Nada por ahora. |
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
