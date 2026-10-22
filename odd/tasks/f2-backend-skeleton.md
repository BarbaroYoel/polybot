# F2 — Esqueleto del backend y contrato real

Fase F2 de `docs/roadmap.md`. Rama: `feat/f2-backend-skeleton` (apilada sobre `feat/f1-pwa-shell`, sin mergear a `main`).
Autorizado por el humano en L1; las decisiones de stack en L2.

## Specs

**S1 — Stack decidido (L2).** Base de datos: «SQLite solo por ahora» — un solo motor, sin servicio externo ni
Docker; migrar a PostgreSQL es una decisión aparte y no se anticipa en el modelo. ORM: «SQLAlchemy 2 + Alembic».
Entorno: «uv». Autenticación: «Sin auth en v0» — la API queda abierta en local, no hay entidad `user` y el
«perfil de usuario» del wireframe sigue decorativo. Testing backend: propuesta registrada en `docs/stack.md`
(`pytest` + `httpx`), aplicada acá; no es una decisión nueva.

**S2 — Alcance de la fase (L1).** `docs/roadmap.md` §F2, literal: «FastAPI con `/health`, configuración tipada,
sobre de error uniforme», «Implementación de `/languages` y `/conversations` con persistencia», «Iteración del
contrato contra la UI, sin romper `docs/api-contract.md`». Verificación de la fase: «la PWA de F1 consume datos
reales en esas dos secciones».

**S3 — `/health` responde exactamente lo del contrato.** `GET /api/v1/health` → `{ "status": "ok", "version": "..." }`,
sin autenticación y sin tocar la base.

**S4 — Todo error sale en el sobre del contrato.** `docs/api-contract.md` §1: «Errores: siempre el sobre del punto
4, nunca HTML ni texto plano». Forma: `{ "error": { "code", "message", "details", "request_id" } }`. `code` estable
y en inglés; `message` en español, accionable. Incluye los 422 de validación de FastAPI (contrato §4: «422 | Error
de validación de esquema (FastAPI)») y cualquier excepción no prevista, que no filtra trazas al cliente.

**S5 — Configuración tipada, sin secretos en el repo.** Variables de `docs/env.example` (`APP_ENV`, `APP_DEBUG`,
`APP_BASE_URL`, `CORS_ORIGINS`, `DATABASE_URL`) cargadas con `pydantic-settings`. App sin `.env` arranca con
defaults de desarrollo seguros; ninguna credencial en código. CORS restringido a `CORS_ORIGINS`.

**S6 — `/languages` implementa la tabla del contrato.** `GET /languages` lista los no archivados; `POST /languages`
agrega (`code`, `level`, `explanation_language`); `PATCH /languages/{id}` cambia nivel, meta o `is_active`, y
activar uno desactiva el anterior (contrato: «Activar uno desactiva el anterior»); `DELETE /languages/{id}` archiva
de forma blanda. Un `code` repetido responde 409, no 500. Campos y tipos según el bloque `LanguageProfile` de
`docs/api-contract.md` §2.

**S7 — `/conversations` implementa la tabla del contrato.** `GET /conversations?language_id=&cursor=` devuelve el
historial del idioma, «más recientes primero», paginado como `{ "items": [...], "next_cursor": null }`;
`POST /conversations` crea (`language_id`, `mode`, `title?`); `GET /conversations/{id}` devuelve la conversación con
sus mensajes paginados; `PATCH /conversations/{id}` renombra; `DELETE /conversations/{id}` elimina. Cada conversación
lleva `message_count` y `last_message_at` del contrato §2.

**S8 — Datos aislados por idioma.** AGENTS.md §3: «Toda consulta de conversaciones, lecciones, planes y progreso se
filtra por `language_id`». Pedir una conversación de otro idioma responde 404 (contrato §4: «Recurso inexistente o
ajeno al idioma activo»), no 403 ni una conversación ajena.

**S9 — La PWA consume datos reales en esas dos secciones.** Inicio (`/`), conversación (`/chat/:id`) y `/languages`
leen de la API en lugar de `frontend/src/lib/fixtures.ts`. Los estados de carga y error ya existen y se usan; los
fixtures quedan solo como datos de ejemplo del seed del backend. Sin backend levantado la UI muestra el estado de
error, no un historial inventado.

**S10 — Documentación al día.** `docs/stack.md` mueve a **Decidido** las filas de base de datos, ORM, gestor de
paquetes, auth y testing backend; `docs/decisions.md` registra ADR-012; `docs/roadmap.md` marca F2; `AGENTS.md` §5
suma los comandos del backend; `docs/open-questions.md` marca Q5 resuelta.

## Assumptions

- SQLite y PostgreSQL comparten el modelo: solo tipos portables (`String`, `Integer`, `Boolean`, `DateTime`,
  `JSON` textual). Nada de `JSONB`, `ARRAY`, `ENUM` nativo ni `UUID` de Postgres, aunque el contrato exponga ids UUID
  como string.
- Los comandos nuevos del backend viven en `backend/` y se documentan en `AGENTS.md` §5 en el mismo commit que los
  introduce.
- `POST /conversations/{id}/messages` y el SSE quedan para F3: sin motor `LLM` no hay turno del tutor. F2 solo
  persiste y lee mensajes existentes (los del seed).

## Tasks

| ID | Qué | Specs | Estado | Commit |
|---|---|---|---|---|
| T1 | Esqueleto: proyecto `uv`, `pyproject.toml`, `ruff`, `pytest`, config tipada, app factory, `request_id`, sobre de error, `/health` | S1, S3, S4, S5 | hecho | `a7adab6` |
| T2 | Persistencia: entidades de dominio, `ports/`, modelos y repositorios SQLAlchemy, migración Alembic inicial, seed con los datos de ejemplo | S1, S6, S7 | hecho | `fc7a812` |
| T3 | API v1: `/languages` y `/conversations` completos, casos de uso en `application/`, tests de integración | S4, S6, S7, S8 | hecho | siguiente unidad |
| T4 | Frontend contra la API: cliente HTTP, tipos del contrato, inicio, conversación y `/languages` con datos reales | S9 | hecho | siguiente unidad |
| T5 | Docs y verificación de la fase: ADR-012, `stack.md`, `roadmap.md`, `api-contract.md`, `AGENTS.md` §5, Q5; suite backend y typecheck/build del frontend | S1, S10 | hecho | cierre |

## Log

**L1** — Pedido original, literal:

> vamos a hacer lo de los commits y luego a implentar F@
>
> vamos a hacer lo de los commits y luego a implentar F2

**L2** — Decisiones de stack, elegidas por el humano en el cuestionario previo a escribir código:

> 1. ¿Qué base de datos usamos desde F2? — **SQLite solo por ahora**
> 2. ¿Y para persistencia? — **SQLAlchemy 2 + Alembic (propuesta registrada)**
> 3. ¿Gestor de paquetes y entorno de Python? — **uv (propuesta registrada)**
> 4. ¿La PWA/API necesita autenticación en v0? — **Sin auth en v0 (propuesta registrada)**

Consecuencias declaradas en las opciones elegidas: migrar a PostgreSQL queda como decisión aparte y `Q5` de
`docs/open-questions.md` queda resuelta sin entidad `user` en el modelo de F2.

**L3** — El commit de la separación inicio / conversación quedó en `e1708e4` sobre `feat/f1-pwa-shell`. F2 se apila
encima de esa rama; integrarla a `main` sigue siendo decisión del humano y no bloquea esta fase.

**L4** — Entorno disponible: `uv 0.11.23`, Python 3.14.4, Node 24.19.0. `docs/stack.md` pide confirmar Python
«3.12 o superior»: se fija `requires-python = ">=3.12"` y el intérprete instalado se usa tal cual.

**L5** — U1 y U3 con RED observado antes del código: los tests del esqueleto fallaron primero con
`ModuleNotFoundError: No module named 'app'`. Para U3, escrito después del código, el verde se validó con dos
mutaciones: quitar la comparación de idioma en `get_conversation_detail` y quitar la desactivación de los otros
idiomas en `PATCH`; cada mutación rompió exactamente su test y revertirla devolvió 37 en verde.

**L6** — El seed falló con `FOREIGN KEY constraint failed`: sin `relationship()`, SQLAlchemy no ordena los
INSERT entre tablas por sí solo. Se resuelve con `flush()` explícito en orden de dependencia (idiomas →
conversaciones → mensajes), no agregando relaciones al mapeo.

**L7** — Cada unidad de trabajo se commitea con su código y sus tests, y su hash se anota en la tabla y el Log en
la unidad siguiente; el cierre (T5) deja la tabla completa con todos los hashes.

**L8** — Decisiones concretas que el contrato no fijaba y que se registran en `docs/api-contract.md` en el mismo
commit que las introduce: `GET /languages` responde un array sin paginar; archivar el idioma activo es 409 (no se
cambia el contexto del usuario en silencio); `GET /conversations/{id}` acepta `language_id` como guarda y
devuelve `messages: { items, next_cursor }`; sin `title` la conversación se crea como «Nueva conversación».
También se agrega la lista cerrada de códigos de error estables.

**L9** — Al escribir los tests de conteo de la base apareció una dependencia implícita: `sqlalchemy` necesita el
extra `asyncio` (greenlet) y SQLite asíncrono necesita `aiosqlite`. Ambas quedan declaradas en `pyproject.toml`.

**L10** — T4 se delegó a un worker acotado (`gentle-ai-worker`) por tamaño de contexto, con superficies de edición
explícitas y sin permiso de commit. Entregó el cliente API, los tipos del contrato, `useAsync`, el provider de
idioma contra el servidor, inicio/chat/`/languages` reales y la limpieza de `fixtures.ts`; reportó explícitamente que
no había verificado en navegador.

**L11** — Esa falta de verificación escondía un defecto real: el probe con Chrome headless encontró que
`/chat/<id>` de una conversación de **otro** idioma caía en «No encontramos esa conversación», porque el frontend
mandaba `language_id` como guarda con el idioma activo. La guarda (S8) es correcta para el contrato, pero
`desing.md` §6.6 pide «cambiar de idioma sin perder la conversación anterior» y §8 que el contexto se actualice. Se
resuelve en la UI: `ChatPage` carga sin guarda y activa el idioma de la conversación (`PATCH is_active`); la guarda
sigue disponible y testeada del lado de la API para cualquier otro consumidor. El probe confirma el cambio de
contexto (Francés/A1 en la cabecera), la persistencia del cambio en el servidor y el 404 de una conversación
inexistente.

**L12** — Cierre de la fase: los cuatro commits de la rama son `a7adab6` (T1), `fc7a812` (T2), `a90d287` (T3) y el
commit de T4; el de T5 es este. La rama F2 queda apilada sobre `feat/f1-pwa-shell`, que sigue sin mergear a `main`:
integrar ambas es decisión del humano.

## Verificación

Todo ejecutado sobre el árbol de trabajo de la rama `feat/f2-backend-skeleton`.

| Qué | Comando | Resultado |
|---|---|---|
| Tests del backend | `uv run pytest` en `backend/` | `37 passed` sobre una base migrada por Alembic |
| Lint y formato | `uv run ruff format --check` · `uv run ruff check` | sin cambios pendientes; `All checks passed!` |
| Significancia de los tests | dos mutaciones sobre `get_conversation_detail` (quitar la guarda) y `PATCH is_active` (quitar la desactivación) | cada una rompió exactamente su test; revertidas → 37 en verde |
| Migración y seed | `uv run alembic upgrade head` · `uv run python -m app.adapters.db.seed` | 3 idiomas, 2 conversaciones, 7 mensajes; la segunda corrida no duplica nada |
| API real | `uvicorn` + `curl` sobre los 9 casos: idiomas, historial, detalle paginado, guarda de idioma ajeno, crear, renombrar, archivar, archivar el activo, cursor inválido | respuestas y códigos de error del contrato |
| Typecheck y build del frontend | `npm run typecheck` · `npm run build` en `frontend/` | sin errores; `✓ built` |
| Sonda en navegador | Chrome headless (`--dump-dom`) contra `vite preview` conectado a la API real: `/`, `/languages`, `/chat/<fr>`, `/chat/<inexistente>` | inicio con el historial real, `/languages` con las acciones, hilo real y cambio de contexto a Francés/A1, recuperación ante id inexistente |
| Sin backend | se detuvo `uvicorn` y se repitió la sonda de `/` | estado de error con «Reintentar», sin conversaciones inventadas |
