# F6.6 — Lecciones con ejercicios de elección

Fase F6.6 de `docs/roadmap.md`, siguiente paso después de F6.5: el chat ya tenía bloques tipados y
las lecciones seguían siendo un formulario de textos. Decisión registrada: ADR-021.
Checks ejecutados: `uv run pytest`, `uv run ruff check`, `uv run ruff format --check`,
`npm run typecheck` y `npm run build`.

## Specs

**S1 — Un segundo tipo de ejercicio, sin romper el primero.** Literal de `desing.md` §6.2:

> - Vista de lección con contenido corto, práctica interactiva y feedback del tutor.

`LessonExercise` gana `kind` (`writing` | `choice`) y `options`. La columna nueva tiene default
`writing`, así que ninguna fila existente cambia de significado y un cliente viejo sigue funcionando.

**S2 — La corrección es una sola.** ADR-017 fijó la comparación determinista para lo escrito; ADR-021
la extiende a lo elegido: el cliente manda el texto de la opción en `answers[].answer` y el servidor
lo compara igual. Mayúsculas, puntuación y espacios no cuentan; los acentos sí. Un `choice` no pasa
por el modelo.

**S3 — La opción correcta no viaja.** El detalle devuelve `options` pero ninguna marca de cuál es la
buena, y `accepted_answers` sigue fuera de la respuesta. La esperada se revela recién en el resultado
de un intento fallido.

**S4 — Contenido consistente.** Un `choice` tiene entre 2 y 6 opciones únicas y exactamente una
respuesta aceptada, que además está entre las opciones. Sin esa regla el ejercicio sería imposible
de acertar o tendría dos respuestas correctas. Se vigila con un test del catálogo, no en runtime.

**S5 — Se lee, no se despliega.** La UI usa un grupo de radios de ancho completo: leer las cuatro
opciones es parte del ejercicio. Sin componentes nuevos, con los tokens de `desing.md` §3.

## Implementación

| Capa | Archivos |
|---|---|
| Dominio | `backend/app/domain/entities.py` (`ExerciseKind`, `LessonExercise.kind/options`) |
| Persistencia | `lesson_exercises.kind` + `options_json`; migración `f7b5c9d3e2a1` |
| Seed | `backend/app/adapters/db/lesson_content.py` (un `choice` por idioma) y `seed.py` |
| API | `LessonExerciseOut.kind` / `.options` (`backend/app/api/v1/schemas.py`) |
| PWA | `frontend/src/features/lessons/LessonPage.tsx`, `lessons.css`, `lib/api/types.ts` |
| Tests | `backend/tests/unit/test_lesson_content.py`, caso nuevo en `test_lessons_api.py` |

## Verificación ejecutada

- `uv run pytest` → **273 passed** (6 nuevos: 5 de integridad del catálogo, 1 de API).
- `uv run ruff format --check` y `uv run ruff check` → limpios.
- `npm run typecheck` → exit 0; `npm run build` → ✓ built in 2.01s.
- Sonda HTTP sobre una base **limpia** migrada y sembrada:
  - `GET /lessons/{id}` de la primera lección francesa → `writing`, `writing`, `writing`, `choice`
    con 4 opciones y sin respuestas aceptadas.
  - Elegir «Comment vas-tu ?» → 3/4, `completed: false`, esperada «Comment allez-vous ?».
  - Elegir «Comment allez-vous ?» → 4/4, `completed: true`.
  - Enviar «comment allez vous» (minúsculas, sin puntuación) → 4/4: la comparación es la misma que
    la de una respuesta escrita.

## Límites conocidos

- El seed **no refresca** un catálogo ya sembrado: `_seed_lessons` salta los idiomas que ya tienen
  unidades, así que una base anterior no ve los ejercicios nuevos sin recrearla (con respaldo).
- `order` (armar la oración) y `listen` (audio) quedan como decisiones aparte; ADR-021 fija dos
  tipos, no una taxonomía cerrada.
- El frontend sigue sin suite propia porque el stack de testing no está decidido (`docs/stack.md`).
- La lección sigue enviando todas las respuestas juntas: no hay corrección por ejercicio antes del
  envío, y eso no cambió en esta fase.
