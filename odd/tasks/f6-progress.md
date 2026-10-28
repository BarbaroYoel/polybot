# F6 — Progreso

Fase F6 de `docs/roadmap.md`; rama `feat/f6-progress`, cortada de `feat/f5-lessons-plans` (`35b0177`).
Checks previstos: `uv run pytest`, `uv run ruff check`, `uv run ruff format --check`,
`npm run typecheck` y `npm run build`.

## Specs

**S1 — Resumen del idioma activo.** Literal de `desing.md` §6.5:

> - Resumen del idioma activo: nivel, sesiones completadas, tiempo practicado y meta semanal.

En v0 **no hay tiempo practicado**: no se guarda duración de mensajes ni de sesiones. Decisión del
humano en L1: la v0 muestra nivel, lecciones completadas y la meta semanal de conversaciones, sin
minutos. No se estima ni se inventa una duración.

**S2 — Evolución por destreza, solo con datos reales.** Literal de `desing.md` §6.5:

> - Evolución por destreza: lectura, escucha, conversación, escritura, vocabulario.

Solo tres destrezas tienen una señal persistida hoy: conversación (conversaciones con mensajes),
escritura (respuestas de ejercicios de lección) y vocabulario (términos sugeridos en el cierre de
turno). Lectura y escucha no dejan registro: se muestran como **no disponibles** con su motivo, no
con un cero que parezca una medición. Decisión del humano en L1.

**S3 — Errores frecuentes.** Literal de `desing.md` §6.5:

> - Lista de **errores frecuentes** y elementos por repasar.

Salen de dos fuentes reales, filtradas por `language_id`: correcciones del cierre de turno y
respuestas incorrectas de intentos de lección. Se agrupan por el par exacto (lo que se escribió, lo
esperado) y se ordenan por recurrencia; nunca se genera un error con el modelo.

**S4 — Historial de prácticas y lecciones.** Literal de `desing.md` §6.5:

> - Historial de prácticas y lecciones.

Se mezclan los intentos de lección y las conversaciones con mensajes, más recientes primero. Cada
fila enlaza a su lección o conversación real.

**S5 — El nivel es un dato, no una medición.** Literal de `desing.md` §6.5:

> - Cambios de nivel basados en una evaluación explícita o criterios trazables; evitar presentar el
>   nivel como una medición infalible.

El nivel se lee del `LanguageProfile` y se muestra como badge. No se calcula, no se propone y no se
cambia desde Progreso: se edita solo en `/languages` con acción explícita (ADR-008). La pantalla lo
dice.

**S6 — Todo por idioma.** `AGENTS.md` §3 y `desing.md` §6.6: resumen, destrezas, errores e historial
se filtran por `language_id`. Un idioma inexistente es 404 `language_not_found`, nunca una lista
vacía silenciosa.

**S7 — Contrato antes que código.** `docs/api-contract.md` §3 ya reserva
`GET /progress?language_id=`; esta fase lo define y documenta en el mismo cambio (AGENTS.md §6.4).

**S8 — Estados reales, ningún botón decorativo.** `desing.md` §8 y §14: la pantalla distingue
cargando, error, sin idioma activo y sin datos suficientes. Con todo en cero y sin historial se
muestra el estado vacío con acciones reales (conversar, abrir lecciones), no tarjetas que finjan un
progreso.

**S9 — Sin esquema nuevo.** Todo se deriva de tablas existentes (`conversations`, `messages`,
`lesson_attempts`, `lesson_attempt_answers`, `message_feedback`, `message_corrections`,
`vocabulary_items`, `lessons`). F6 no agrega migración ni escribe datos.

## Contrato

`GET /api/v1/progress?language_id=<uuid>&tz=<IANA>` — `tz` opcional, por defecto `UTC`.

```jsonc
{
  "language": { "id": "uuid", "code": "fr", "name": "Francés", "level": "A1" },
  "summary": {
    "level": "A1",
    "lessons_completed": 2,
    "lessons_total": 12,
    "conversations": 5,
    "weekly_goal": { "conversations": 3, "target": 7 }
  },
  "skills": [
    { "id": "conversation", "available": true, "count": 4, "last_at": "..." },
    { "id": "writing", "available": true, "count": 17, "last_at": "..." },
    { "id": "vocabulary", "available": true, "count": 9, "last_at": "..." },
    { "id": "reading", "available": false, "count": null, "last_at": null },
    { "id": "listening", "available": false, "count": null, "last_at": null }
  ],
  "frequent_errors": [
    { "kind": "correction", "prompt": null, "original": "je suis allé",
      "expected": "je suis allée", "count": 2, "last_at": "..." },
    { "kind": "lesson", "prompt": "Pedir el menú", "original": "je voudrais un cafe",
      "expected": "je voudrais un café", "count": 1, "last_at": "..." }
  ],
  "history": [
    { "kind": "lesson", "id": "uuid", "title": "Pedir algo en un café", "at": "...",
      "correct": 3, "total": 3, "message_count": null },
    { "kind": "conversation", "id": "uuid", "title": "Pedir un café", "at": "...",
      "correct": null, "total": null, "message_count": 12 }
  ]
}
```

Reglas exactas:

1. `summary.lessons_completed` = lecciones del idioma con al menos un intento aprobado (la misma
   derivación de `LessonRepository.lesson_statuses`). `lessons_total` = lecciones del catálogo.
2. `summary.conversations` = conversaciones del idioma con al menos un mensaje. Una conversación
   vacía no es práctica y no cuenta.
3. `weekly_goal.conversations` = conversaciones distintas con al menos un mensaje desde el lunes
   00:00 de `tz`; `target` = `weekly_goal.conversations` del perfil. La semana empieza el lunes.
4. `skills` siempre trae las cinco, en ese orden. `last_at` es la fecha de la última señal o `null`.
5. `frequent_errors`: hasta 5, ordenados por `count` descendente y luego `last_at` descendente.
   `correction` agrupa por (`original`, `corrected`) exactos; `lesson` agrupa por (`prompt`,
   `answer`, `expected`) exactos. `prompt` es `null` en `correction`.
6. `history`: hasta 10, más reciente primero. Un ítem `lesson` por intento, con `correct`/`total`;
   una `conversation` por conversación con mensajes, con `message_count`. `at` es ISO 8601 UTC.
7. Idioma inexistente → 404 `language_not_found`. `tz` inválida → 400 `invalid_timezone` con mensaje
   accionable. Sin datos → 200 con ceros, listas vacías y destrezas disponibles en `count: 0`.

## Tasks

| ID | Specs | Ruta y alcance | Estado |
|---|---|---|---|
| T1 | S3, S6, S7, S9 | Backend: entidades de lectura, puerto `ProgressRepository`, adaptador SQLAlchemy, `ProgressService`, `GET /progress`, esquemas, errores, dependencia y tests | completada; 221 tests verdes |
| T2 | S1, S2, S4, S5, S8 | PWA: cliente y tipos, `ProgressPage`, estilos, ruta y estados | completada; typecheck y build verdes |
| T3 | todas | Verificación ejecutada, contrato/ADR/roadmap y cierre con límites explícitos | completada; sonda HTTP contra base aislada |

## Log

**L1 — arranque de F6.** El humano pidió, literal:

> quiero seguir trabando en esrte proyecto

Se trajeron las ramas de la nube (`feat/f1-pwa-shell`, `feat/f2-backend-skeleton`,
`feat/f3-real-text-chat`, `feat/f5-lessons-plans`) y se cortó `feat/f6-progress` desde el tip de F5
(`35b0177`). Ante dos huecos de datos, el humano decidió:

1. **Sin minutos en v0**: no se mide tiempo; la meta semanal queda en conversaciones.
2. **Solo las tres destrezas con datos reales**: lectura y escucha se muestran como no disponibles.

Después pidió, literal: «no me hagas mas pregutas sigie trabajando , y lanza subagentes». Se fija el
contrato y se delegan T1 (backend) y T2 (PWA) en paralelo, con archivos disjuntos; el orquestador
conserva contrato, ADR y roadmap. No se instalan dependencias por iniciativa propia (AGENTS.md §5):
`uv` y `node_modules` no están en este entorno.

**L2 — T1 y T2 entregadas; revisión del orquestador.** Dos subagentes trabajaron en paralelo con
archivos disjuntos; el orquestador revisó el diff completo antes de aceptarlo.

Backend:

- `backend/app/domain/entities.py`: `SkillId`, `ActivityCount`, `SkillProgress`, `FrequentErrorKind`,
  `FrequentError`, `HistoryKind`, `HistoryEntry` (puros, con los límites de ADR-018 en los docstrings).
- `backend/app/domain/errors.py`: `InvalidTimezone`.
- `backend/app/ports/repositories.py`: puerto `ProgressRepository` de solo lectura.
- `backend/app/adapters/db/progress.py`: agregados SQL por `language_id`, sin escritura y sin N+1.
- `backend/app/application/progress.py`: `week_start` con `zoneinfo`, `ProgressSummary`,
  `ProgressView` y `ProgressService`.
- `backend/app/api/v1/progress.py`, `schemas.py`, `errors.py`, `router.py` y `core/dependencies.py`:
  endpoint fino, modelos Pydantic, 400 `invalid_timezone` y composición.
- `backend/tests/integration/test_progress_api.py` (12 escenarios) y
  `backend/tests/unit/test_progress_week.py` (5 escenarios).

PWA:

- `frontend/src/lib/api/types.ts` y `frontend/src/lib/api/progress.ts`.
- `frontend/src/features/progress/ProgressPage.tsx` y `progress.css`.
- `frontend/src/features/sections/pages.tsx` (se retira el placeholder) y `frontend/src/app/App.tsx`.

Decisiones de implementación, reversibles:

1. `tz` por defecto `UTC`; zona inválida → 400 `invalid_timezone`, nunca un fallback silencioso. El
   idioma se valida antes que la zona, así un idioma inexistente gana como 404.
2. La semana empieza el lunes 00:00 local y se convierte a UTC naive para comparar con las fechas
   guardadas.
3. Errores e historial se limitan en cada fuente y se mezclan en memoria: un ítem fuera del top-N de
   su propia fuente no puede entrar al top-N global.
4. `writing` cuenta respuestas de ejercicios enviadas, no intentos: es la unidad que el usuario
   produjo. `vocabulary` cuenta términos sugeridos, no «aprendidos».
5. La UI no muestra minutos ni «tiempo practicado»; el nivel es un badge con enlace a `/languages`.

Verificación ejecutada en este entorno:

- `python3 -m compileall -q backend/app backend/tests` → OK (antes de instalar dependencias).
- `week_start` ejecutado a mano: UTC, lunes 23:59, `Pacific/Kiritimati` (lunes local en domingo UTC),
  `Pacific/Honolulu` y las zonas inválidas `""`, `No/Existe`, `../etc/passwd` → valores y errores
  esperados.
- `ProgressService` con puertos falsos: resumen, cinco destrezas (3 disponibles, 2 no), errores,
  historial y 404 de idioma ajeno → OK.
- `git diff --check` → OK; líneas nuevas dentro de 100 columnas; ningún color hardcodeado en la
  pantalla.

**L3 — autorización para instalar y verificación completa.** El humano pidió, literal:

> hazlo , no empieces f7 todavia

Se instalaron las dependencias declaradas (`uv sync`, `npm install`; sin agregar paquetes nuevos) y se
corrieron las suites:

- `uv run pytest` → **221 passed in 34.28s** (203 previos + 18 nuevos).
- `uv run ruff format --check` → 3 archivos nuevos reformateados y luego 101 archivos limpios;
  `uv run ruff check` → All checks passed.
- `npm run typecheck` → exit 0.
- `npm run build` → ✓ built in 2.48s.
- Sonda `python3 /tmp/verify_f6.py` contra `uvicorn` en el puerto 8010, con base SQLite aislada,
  `alembic upgrade head` y seed real. Resultados observados:
  - Francés: `1/4` lecciones completadas tras un intento fallido y uno perfecto, 1 conversación,
    `writing: 3` respuestas, 3 errores frecuentes, 3 filas de historial.
  - Aleman: una conversación creada por la sonda y un mensaje enviado cuentan 1 en la meta semanal;
    la meta semanal francesa sigue en 0 (aislamiento por idioma).
  - `tz=No/Existe` → 400 `invalid_timezone`; idioma inexistente → 404 `language_not_found`.
  - Destrezas en orden fijo: 3 disponibles con contador y 2 no disponibles con `count: null`.

**Sonda de navegador y URL pública (L4):**

1. Chromium headless (Playwright) sobre la PWA real, 1280×900 y 375×812: resumen, cinco destrezas,
   errores e historial visibles; sin errores de consola; sin desborde horizontal
   (`scrollWidth == innerWidth == 375`); todas las llamadas a `/api/v1` salieron por el proxy de Vite
   en el origen de la PWA. Capturas en `/tmp/f6-progress-desktop.png` y `/tmp/f6-progress-mobile.png`.
2. URL pública de Codespaces verificada: `https://<codespace>-5173.app.github.dev` devolvió 200 con la
   app y respondió `/api/v1/health` y `/api/v1/progress` a través del proxy. Se puso `public` solo para
   la comprobación anónima y se volvió a `private`.
3. Ajustes locales necesarios, no versionados salvo el primero:
   - `frontend/vite.config.ts`: `allowedHosts: [".app.github.dev"]` en `server` y `preview`, más el
     proxy `/api` también en `preview`.
   - `frontend/.env.local` (ignorado): `VITE_API_BASE_URL=/api/v1`.
   - `gh codespace ports forward 5173:15173 -c <codespace>` mantiene el puerto registrado mientras la
     sesión siga viva.

**Pendiente y límites, no silenciosos:**

1. El frontend sigue sin suite propia: el stack de testing está sin decidir (`docs/stack.md`).
2. `npm audit` reporta 4 vulnerabilidades (3 moderadas, 1 alta) en dependencias de desarrollo. No se
   corrió `npm audit fix` para no cambiar versiones fuera del alcance de F6.
3. La API no tiene autenticación todavía (`docs/open-questions.md` Q5): el puerto 5173 debe quedar en
   `private`; ponerlo `public` expone lectura y escritura a quien tenga la URL.
4. La fase no commitea: queda en el árbol de `feat/f6-progress` a la espera del pedido de entrega.
