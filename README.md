# Polybot

PWA de tutor de idiomas guiada por IA, centrada en el chat, con la voz como capacidad de primera
clase. Un solo idioma activo a la vez; conversaciones, lecciones, planes y progreso aislados por
idioma.

**Estado:** F1–F7 completas. F7 (intérprete en tiempo real) está en la rama
`feat/f7-live-interpreter`, con `uv run pytest` (292 passed), Ruff, typecheck, build y una sonda de
navegador con micrófono falso. La fuente de verdad del avance y de la evidencia de cada fase es
[`docs/roadmap.md`](./docs/roadmap.md); el detalle tarea por tarea está en [`odd/tasks/`](./odd/tasks).

Lo que ya funciona de punta a punta: la PWA lee idiomas y conversaciones de la API, conversa con el
tutor en tiempo real por SSE, pide correcciones y vocabulario al cerrar cada turno, traduce un mensaje
o un fragmento seleccionado, transcribe y reproduce voz con motores locales, completa lecciones con
corrección determinista, errores, vocabulario y planes de estudio por semanas con el estado de cada
sesión derivado de los intentos, consulta su progreso real por idioma, y traduce texto o interpreta
voz en vivo por WebSocket con transcripción y traducción por segmentos.

## Requisitos

| Pieza | Para qué | Nota |
|---|---|---|
| Python 3.13 + [uv](https://docs.astral.sh/uv/) | backend | `uv sync` instala todo |
| Node 20+ | frontend | solo el frontend |
| [Pi](https://github.com/badlogic/pi) en el `PATH` | tutor por defecto (ADR-013) | sin Pi en el `PATH`, el chat y la traducción responden `llm_unavailable`, y la lección se corrige igual sin comentario; idiomas, catálogo y planes siguen funcionando |
| [OpenCode](https://opencode.ai) CLI (`opencode`) | tutor alternativo (ADR-019) | activalo con `LLM_PROVIDER=opencode`; requiere un proveedor/modelo ya autenticado en OpenCode (`OPENCODE_MODEL`) |
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
backend está en [`docs/env.example`](./docs/env.example); copiala a `.env` y ajustá el proveedor del
tutor. Por defecto usa **Pi**; para usar **OpenCode**:

```dotenv
LLM_PROVIDER=opencode
OPENCODE_MODEL=proveedor/modelo
OPENCODE_AGENT=plan
OPENCODE_TRANSLATION_AGENT=general
```

`OPENCODE_MODEL` es obligatorio en la práctica: cada instalación de OpenCode autoriza proveedores
distintos y su modelo por defecto puede no estar habilitado (ADR-019). La traducción usa su propio
agente (`general`) porque `plan` narra su rol en vez de traducir (F7 T6).

El intérprete de voz vive en `WS /api/v1/voice/interpret`; el proxy de Vite ya reenvía WebSocket
(`ws: true`) y el micrófono solo se pide al pulsar «Iniciar micrófono». El audio no se guarda.

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
| [`docs/decisions.md`](./docs/decisions.md) | ADRs aceptadas (ADR-001 a ADR-019). |
| [`docs/open-questions.md`](./docs/open-questions.md) | Decisiones de producto/UI todavía abiertas. |
| [`docs/roadmap.md`](./docs/roadmap.md) | Fases F0–F7, qué se verificó en cada una y qué falta. |
| [`odd/tasks/`](./odd/tasks) | Una ficha por feature: specs, tareas, commits y evidencia. |
| [`grayscale_language_tutor_chat_ui.png`](./grayscale_language_tutor_chat_ui.png) | Wireframe de referencia (1448×1086). |

## Stack

Frontend **React 18 + Vite + TypeScript**, CSS propio sobre los tokens de `desing.md` §3.
Backend **FastAPI** con capas `domain → application → adapters`, **SQLite** por SQLAlchemy 2 + Alembic.
Tutor: **Pi por defecto u OpenCode como alternativa**, elegido con `LLM_PROVIDER` (ADR-013,
ADR-019). Voz: **Whistle** local (STT) y **Piper** por binario (TTS), detrás de los puertos `STT` y
`TTS`. La UI no conoce ningún orquestador: solo habla con la API.

Las decisiones y sus motivos están en [`docs/decisions.md`](./docs/decisions.md); cada una dice qué
alternativa se descartó y por qué.

## Skills del proyecto

`.agents/skills` incluye `frontend-design`, `ui-ux-pro-max` y `web-design-guidelines`.
El índice generado está en `.atl/skill-registry.md`.

## Licencia

Sin definir: el repositorio es público para leerlo y revisarlo, pero todavía no hay una licencia que
otorgue derechos de uso, copia o derivados.
