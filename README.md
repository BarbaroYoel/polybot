# Polybot

PWA de tutor de idiomas guiada por IA, centrada en el chat, con la voz como capacidad de primera
clase. Un solo idioma activo a la vez; conversaciones, lecciones, planes y progreso aislados por
idioma.

**Estado:** F4 (voz) completada; F5 (lecciones y planes) completada en la rama
`feat/f5-lessons-plans` (`8ba8964`, `00d8dcb`). La fuente de verdad del avance y de la evidencia de
cada fase es [`docs/roadmap.md`](./docs/roadmap.md); el detalle tarea por tarea está en
[`odd/tasks/`](./odd/tasks).

Lo que ya funciona de punta a punta: la PWA lee idiomas y conversaciones de la API, conversa con el
tutor en tiempo real por SSE, pide correcciones y vocabulario al cerrar cada turno, traduce un mensaje
o un fragmento seleccionado, transcribe y reproduce voz con motores locales, y completa lecciones con
corrección determinista, errores, vocabulario y planes de estudio por semanas con el estado de cada
sesión derivado de los intentos.

## Requisitos

| Pieza | Para qué | Nota |
|---|---|---|
| Python 3.13 + [uv](https://docs.astral.sh/uv/) | backend | `uv sync` instala todo |
| Node 20+ | frontend | solo el frontend |
| [Pi](https://github.com/badlogic/pi) en el `PATH` | el tutor es una instancia de Pi por turno (ADR-013) | sin Pi en el `PATH`, el chat y la traducción responden `llm_unavailable`, y la lección se corrige igual sin comentario; idiomas, catálogo y planes siguen funcionando |
| Piper (binario) + voces | audio de salida (ADR-016) | opcional: sin él, `/voice/speech` responde `tts_unavailable` |
| `cactus-needle` | audio de entrada, modelo Whistle (ADR-015) | entra por `uv sync`; el modelo se baja con el primer uso |

## Cómo correrlo

Backend (`http://localhost:8000`, la API vive en `/api/v1`):

```bash
cd backend
uv sync
uv run alembic upgrade head          # crea el esquema
uv run python -m app.adapters.db.seed # datos de ejemplo: idiomas, conversaciones y lecciones
uv run uvicorn app.main:app --reload
```

Frontend (`http://localhost:5173`):

```bash
cd frontend
npm install
npm run dev
```

`VITE_API_BASE_URL` (en `frontend/.env`) cambia el destino de la API. La plantilla de variables del
backend está en [`docs/env.example`](./docs/env.example).

## Checks

```bash
cd backend  && uv run pytest && uv run ruff format --check && uv run ruff check
cd frontend && npm run typecheck && npm run build
```

La suite del backend corre sobre una base migrada por Alembic, sin red: el proveedor del tutor y los
motores de voz se reemplazan por dobles. Los comandos válidos están en [`AGENTS.md`](./AGENTS.md) §5.

## Qué hay en este repositorio

| Archivo | Para qué |
|---|---|
| [`desing.md`](./desing.md) | Fuente de verdad de producto y UI: pantallas, estados, tokens, criterios de aceptación. |
| [`AGENTS.md`](./AGENTS.md) | Contrato de trabajo para agentes (Pi, OpenCode, Codex, Cursor…). Empezá por acá si sos un agente. |
| [`docs/architecture.md`](./docs/architecture.md) | Capas, límites, mapa de carpetas y flujos. |
| [`docs/stack.md`](./docs/stack.md) | Qué está decidido y qué falta decidir. |
| [`docs/api-contract.md`](./docs/api-contract.md) | Contrato entre frontend y backend. |
| [`docs/conventions.md`](./docs/conventions.md) | Código, tests, commits, idioma de artefactos. |
| [`docs/decisions.md`](./docs/decisions.md) | ADRs aceptadas (ADR-001 a ADR-017). |
| [`docs/open-questions.md`](./docs/open-questions.md) | Decisiones de producto/UI todavía abiertas. |
| [`docs/roadmap.md`](./docs/roadmap.md) | Fases F0–F7, qué se verificó en cada una y qué falta. |
| [`odd/tasks/`](./odd/tasks) | Una ficha por feature: specs, tareas, commits y evidencia. |
| [`grayscale_language_tutor_chat_ui.png`](./grayscale_language_tutor_chat_ui.png) | Wireframe de referencia (1448×1086). |

## Stack

Frontend **React 18 + Vite + TypeScript**, CSS propio sobre los tokens de `desing.md` §3.
Backend **FastAPI** con capas `domain → application → adapters`, **SQLite** por SQLAlchemy 2 + Alembic.
Tutor: **una instancia de Pi por turno** detrás del puerto `LLM`. Voz: **Whistle** local (STT) y
**Piper** por binario (TTS), detrás de los puertos `STT` y `TTS`. La UI no conoce ningún orquestador:
solo habla con la API.

Las decisiones y sus motivos están en [`docs/decisions.md`](./docs/decisions.md); cada una dice qué
alternativa se descartó y por qué.

## Skills del proyecto

`.agents/skills` incluye `frontend-design`, `ui-ux-pro-max` y `web-design-guidelines`.
El índice generado está en `.atl/skill-registry.md`.

## Licencia

Sin definir: el repositorio es público para leerlo y revisarlo, pero todavía no hay una licencia que
otorgue derechos de uso, copia o derivados.
