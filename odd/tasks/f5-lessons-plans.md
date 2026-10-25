# F5 — Lecciones y planes de estudio

Fase F5 de `docs/roadmap.md`. Autorizada en L1: el humano pidió continuar con la fase siguiente a F4.
Sin commits: `AGENTS.md` §6.7 lo prohíbe salvo pedido explícito.

## Specs

**S1 — Catálogo por idioma, con la lección siguiente destacada.** Literal de `desing.md` §6.2:

> - Cabecera con idioma y nivel actual.
> - Tarjeta destacada **Continuar aprendiendo**.
> - Lista de unidades: vocabulario, gramática, pronunciación, escucha y práctica situacional.
> - Cada lección muestra título, tipo, dificultad, duración estimada y estado.

Y de `desing.md` §12: «`Lesson`: idioma, tema, dificultad, ejercicios y resultado».

**S2 — Lección con práctica y feedback.** Literal de `desing.md` §6.2:

> - Vista de lección con contenido corto, práctica interactiva y feedback del tutor.
> - Al finalizar: resultado, errores relevantes, vocabulario nuevo y próxima recomendación.

**S3 — Plan a partir de un objetivo.** Literal de `desing.md` §6.3:

> - Mostrar **objetivo** (ej. «Pasar de A1 a B1 en francés»).
> - Frecuencia de estudio y tiempo diario configurables.
> - Calendario o cronograma sencillo por semanas.
> - Lista de sesiones con estado: pendiente, en curso, completada.
> - Acción primaria «Continuar plan» y acción secundaria «Ajustar plan».

**S4 — El tutor puede proponer ajustes, el humano los acepta.** Literal de `desing.md` §6.3:
«El tutor puede **proponer** cambios basados en el rendimiento; mostrar los cambios importantes al
usuario para aceptarlos.» En v0 el ajuste es explícito del usuario («Ajustar plan»): el servidor
recalcula el cronograma y **nunca** cambia el plan sin que el humano lo pida.

**S5 — Estados reales, ningún botón decorativo.** `desing.md` §8 y AGENTS.md §3: la pantalla no
muestra una tarjeta que no haga algo. «Continuar aprendiendo» abre la lección siguiente de verdad;
sin lecciones para el idioma activo se muestra el estado vacío con su motivo. Las sesiones derivan su
estado de los intentos reales: `completada` si hay un intento aprobado, `en curso` si hay un intento
sin aprobar, `pendiente` si no hay intento. Nada de estados inventados por la UI.

**S6 — Nada se inventa sobre el progreso del idioma.** AGENTS.md §3 («Datos por idioma») y
`desing.md` §6.5: toda consulta de lecciones, intentos y planes se filtra por `language_id`; un
idioma ajeno es 404, no una lista vacía silenciosa.

**S7 — Contrato antes que código.** `docs/api-contract.md` §3 filas de «Aprendizaje» ya fijan
`GET /lessons?language_id=`, `GET /lessons/{id}`, `POST /lessons/{id}/submit`, `GET /plans?language_id=`
y `POST /plans`; el ajuste del plan necesita `PATCH /plans/{id}` y se documenta en el mismo cambio
(AGENTS.md §6.4). `GET /progress?language_id=` **no** se implementa acá: es F6, aunque los intentos se
persisten ahora para que F6 los lea.

**S8 — Contenido de la v0: catálogo sembrado, corrección determinista.** `desing.md` §13 pone
«generación de lecciones» **después** de la base: la v0 sirve un catálogo de lecciones y ejercicios
como **datos sembrados** por idioma, y la corrección de cada respuesta es **determinista** (respuesta
aceptada normalizada: sin mayúsculas, sin acentos, sin puntuación). El proveedor del tutor (el mismo
puerto `LLM` de F3) aporta el comentario de cierre y es **best-effort**: si falla, la lección se
corrige igual y el comentario queda `null`. Decisión registrada en ADR-017.

**S9 — La voz del tutor no reemplaza al texto.** `docs/roadmap.md` F4 (verificación) y AGENTS.md §3:
el contenido de la lección es texto en el idioma practicado; el comentario del tutor llega en el
idioma de explicación del perfil del idioma.

## Tasks

| ID | Specs | Ruta | Commit |
|---|---|---|---|
| T1 | S1, S6, S8 | Unidades, lecciones y ejercicios en el dominio + esquema + seed por idioma + `GET /lessons?language_id=` | `0ca0673` |
| T2 | S2, S7, S8 | `GET /lessons/{id}` + `POST /lessons/{id}/submit`: corrección determinista, intento persistido, comentario del tutor best-effort | `0ca0673` (mismo commit que T1) |
| T3 | S3, S4, S6 | Planes: dominio, esquema, `GET /plans?language_id=`, `POST /plans`, `PATCH /plans/{id}` con cronograma por semanas y estados derivados | `bf2dca7` |
| T4 | S1, S2, S3, S5 | PWA: catálogo de lecciones, vista de lección con práctica y resultado, pantalla de plan con sesiones | pendiente |
| T5 | todas | Checks de la fase, verificación en navegador contra la API real y documentación (contrato, roadmap, decisiones) | pendiente |

## Log

**L1 — pedido original, literal:**

> en que estado estamos , contienua con la siguiente fase , no hagas preguntas

**L2 — la fase anterior quedó cerrada antes de abrir esta.** `odd/tasks/f4-voice.md` L7 registra el
turno de voz completo medido (transcribir 2,81 s en frío y 0,19 s en caliente, turno del tutor 11,31 s
con primer token a 4,23 s, síntesis 0,32 s y caché en 0,00 s) y `docs/roadmap.md` marca F4 como
completada, dejando explícito como pendiente el streaming por frases y el warm-up del motor.

**Decisiones tomadas en esta fase que el humano puede revertir:**

1. **Contenido sembrado, no generado** (S8, ADR-017). Es lo que `desing.md` §13 deja para después; la
   alternativa —generar el catálogo con el modelo— no es testeable ni estable por idioma.
2. **Práctica de v0 = producir texto en el idioma**, corregido de forma determinista. `desing.md`
   §6.2 pide «práctica interactiva» sin fijar el tipo de ejercicio; el texto libre es lo que el
   producto ya hace bien y lo único que se corrige sin heurísticas.
3. **Estado de cada sesión derivado de los intentos** (S5), sin endpoint extra: un botón que cambie
   estados a mano sería un botón decorativo.

**L3 — T1 y T2 entraron en un solo commit, y el ADR-017 se escribió tarde.** Al cortar la historia
(el árbol arrastraba F3.5, F4 y F5 sin commit) T1 y T2 resultaron inseparables sin inventar código
intermedio: comparten migración, repositorio, servicio y archivo de tests, y el catálogo deriva su
estado de los intentos que crea el submit. Se commitearon juntos en `0ca0673`; F3.5 y F4 quedaron en
`636c0eb` y `5b647f6`. El ADR-017 estaba citado en tres lugares (S8, este log y
`lesson_content.py`) y no existía en `docs/decisions.md`: se escribió en el mismo commit.

**L4 — T3 cerrado: lo que se verificó y lo que queda anotado.** Escrito test-first: los 10 tests de
`backend/tests/integration/test_plans_api.py` se vieron fallar (10 failed) antes de la primera línea
de implementación, y pasan (10 passed) con la suite completa en **201 passed**, `ruff format`/`ruff
check` limpios en todo el proyecto y la migración `c4e7b1a9d3f2` probada con `alembic upgrade head` y
`downgrade -1` sobre una base aparte. Límites conocidos, no silenciosos:

1. **Carrera al crear dos planes del mismo idioma**: el 409 sale del chequeo del servicio; la
   restricción `UNIQUE` es la red de contención, pero el adaptador no traduce un `IntegrityError`,
   así que una carrera real daría 500 `internal_error`. v0 es de un solo usuario y no tiene postura
   de concurrencia; queda anotado, no resuelto.
2. `PlanSessionState` repite los tres valores de `LessonStatus` a propósito: el estado de una sesión
   es vocabulario del plan, no de la lección. Si un revisor prefiere reusar `LessonStatus`, es un
   cambio de una línea.
3. `docs/api-contract.md` §1 no listaba `lesson_not_found` ni `missing_lesson_answers` de T1/T2: se
   agregaron en el commit de T3.
4. El archivo de tests de planes se formateó con `ruff format` después de escribirlo (solo saltos de
   línea; el hash del AST es idéntico antes y después), porque el gate de lint del proyecto es
   global y no hay excepciones por archivo.
