# F5 — Lecciones y planes de estudio

Fase F5 de `docs/roadmap.md`; rama `feat/f5-lessons-plans`. Continuación autorizada en L1, L5 y L8.
Entrega elegida por el humano en L10: `chain_strategy=feature-branch-chain` sobre esta rama.
Checks: `npm run typecheck`, `npm run build`, `uv run pytest` y navegador contra API aislada.

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

| ID | Specs | Ruta y alcance | Estado | Commit / evidencia |
|---|---|---|---|---|
| T1 | S1, S6, S8 | Unidades, lecciones y ejercicios en el dominio + esquema + seed por idioma + `GET /lessons?language_id=`; ruta histórica no registrada | completada | `0ca0673` |
| T2 | S2, S7, S8 | `GET /lessons/{id}` + `POST /lessons/{id}/submit`: corrección determinista, intento persistido, comentario del tutor best-effort; ruta histórica no registrada | completada | `0ca0673` (mismo commit que T1) |
| T3 | S3, S4, S6 | Delegada: planes, dominio, esquema, `GET /plans?language_id=`, `POST /plans`, `PATCH /plans/{id}` con cronograma por semanas y estados derivados | completada | `bf2dca7`; L4 |
| T4 | S1–S9 | Delegada por pedido explícito y context backstop: PWA, catálogo de lecciones, práctica y resultado, plan con sesiones y enlaces reales desde inicio | completada | `8ba8964`; typecheck, build, 201 tests y probes aislados; L6 |
| T5 | todas | Delegada por pedido explícito y context backstop: corregir los dos problemas de L7, comprobar lo afectado y cerrar documentación | completada | `00d8dcb` (arreglo del proveedor) y este commit de docs; 203 tests, Ruff, typecheck y build limpios; verificación independiente en copia aislada; L9 |

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

**L5 — continuación autorizada, pedido literal:**

> vamosn a continuar con F5 , lanza un agente

Se retoma en `ee8f4f6`, con árbol limpio: T1–T3 conservan sus commits y evidencia; T4 y T5 siguen
abiertas. La búsqueda de la copia completa `odd/f5-lessons-plans/tasks` en Engram no devolvió una
copia recuperable: se reconstruye desde este archivo, sin descartar el progreso existente.
T4 se delega a `gentle-ai-worker` por pedido explícito y por el context backstop del runtime.
El alcance sigue siendo F5 y los endpoints existentes: no se abre F6, no se agrega una dependencia,
no se cambia `desing.md` ni se toca la base de uso cotidiano. El agente no hace commits ni push.
El orquestador mantiene este documento y su espejo; T4 solo se cierra con checks observados y T5
requiere verificación funcional en navegador, no solamente typecheck o build.

**L6 — T4 verificada; T5 en curso.** El primer lanzamiento del agente falló sin tocar código.
El humano pidió literalmente:

> continua

Se retomó la misma asignación. El agente implementó catálogo, práctica/resultado, planes y enlaces
de inicio. Reportó `npm run typecheck` y `npm run build` con exit 0, y `uv run pytest` con exit 0
(**201 passed in 12.98s**). Sus probes de Chrome contra una base aislada observaron las pantallas
F1 antes del cambio (RED), y luego catálogo, intento parcial/completo, creación/ajuste de plan,
aislamiento por idioma, catálogo vacío, plan sin sesiones y ausencia de overflow a 375×812 y
1280×900 (GREEN). El orquestador leyó el diff de las superficies compartidas, ejecutó
`git diff --check` (exit 0) y repitió `npm run typecheck` (exit 0).

ASSESS devolvió `nativeRisk: unassessable` por archivos nuevos sin declaración explícita y el plan
`writerSelfVerification: true`, `independentVerifier: false`; no se inventó una clasificación ni
se inició una revisión nativa. No se identificó un ítem de alto riesgo: se agregaron tipos/rutas,
sin cambiar helpers, backend, contratos, dependencias ni la base de uso cotidiano. La implementación
coherente ronda 2,3k líneas, superior a la heurística de 400: no se recortaron tests o documentación
para reducir el conteo. Sigue sin commits.

T5 toma la verificación final en estado aislado, incluido el comentario del tutor `null` por fallo
del proveedor, y la documentación. No se inventan fechas concretas: el contrato define semanas y
orden de sesiones, no días de calendario. F5 no se marca completa antes de observar esa evidencia.

**L7 — cierre parcial y decisión necesaria.** El agente de T5 terminó con
`timed_out: stalled for 4 min after: edit`, sin devolver un dictamen final. Alcanzó a editar
`README.md`, crear `frontend/README.md` y actualizar la sección F5 del roadmap. Allí dejó anotados
el flujo plan → lección → recarga y un submit 200 con `feedback: null` ante un proveedor que sale
con error; también registró dos problemas: numeración nativa y propia duplicada en las listas, y
`PI_BIN_PATH` inexistente que provoca 500 `internal_error` en vez de comentario opcional.

Son anotaciones del agente, no un cierre final observado por el orquestador. No se reinició el
agente ni se lanzaron más verificaciones tras el timeout. Se corrigieron los resúmenes de estado
del README y del roadmap para no afirmar un cierre completo ni seguir diciendo que falta la PWA.
T4 conserva la evidencia válida de L6. T5 queda bloqueada a la espera de la decisión humana:
autorizar un nuevo intento acotado para esas dos correcciones y sus comprobaciones afectadas,
o conservar F5 explícitamente parcial. No se modificó backend ni se hicieron commits o push.

**L8 — intento acotado autorizado, pedido literal:**

> si hazlo

El humano acepta corregir los dos problemas reportados y comprobar únicamente lo afectado.
Se conserva T4 y su evidencia; se reabre T5 sin cambiar S1–S9 ni abrir F6. El nuevo agente debe
reproducir ambos problemas antes de editar, preservar el contrato del chat y de traducción si toca
el adaptador compartido de Pi, y dejar un test público de regresión para el ejecutable inexistente.
Las sondas usan estado aislado; no se modifica la base habitual, no se instalan dependencias y no
se hacen commits ni push. Un nuevo timeout es un fallo, no permiso para reintentos automáticos.
El orquestador evalúa el diff y aplica la verificación independiente solo si hay un ítem concreto
de alto riesgo; el agente no gestiona revisión nativa ni el espejo de este documento.

**L9 — T5 cerrada: qué se corrigió y con qué evidencia.** El worker de L8 volvió a terminar con
error del arnés, pero dejó los cambios del backend y sus tests; el orquestador verificó el diff en
lugar de asumir su reporte. ASSESS devolvió tier alto al escalar el ítem 3 (el adaptador de Pi lo
comparten chat y traducción), así que se ejecutó la verificación independiente que corresponde.

Correcciones:

1. `PiCliAdapter` envuelve el arranque del subproceso y traduce un `OSError` a `LlmUnavailable`, con
   limpieza del directorio temporal y log sin datos sensibles. La corrección se reprodujo primero:
   sin el bloque, los dos tests nuevos fallan con `FileNotFoundError`; con él, pasan.
2. `list-style: none; margin: 0; padding: 0` en `.unit__lessons`, `.practice__list`,
   `.plan__weeks` y `.plan__sessions`: cada fila conserva solo su número propio.

Evidencia observada (orquestador salvo indicación):

- `uv run pytest` **203 passed in 13.42s**; `uv run ruff check` y `uv run ruff format --check`
  limpios (el agente había dejado un archivo sin formatear, corregido con `ruff format`).
- `npm run typecheck` exit 0 y `npm run build` ✓ built in 780ms.
- Verificación independiente en una copia `mktemp -d` con su propia base migrada y sembrada:
  `POST /lessons/{id}/submit` con `PI_BIN_PATH` inexistente devuelve **200** con 3/3, intento
  persistido, `feedback: null`, próxima lección avanzada y francés intacto; el chat emite
  `llm_unavailable` por SSE y la traducción responde 502 con el mismo código, sin 500.
- En Chrome headless con métricas de dispositivo: `list-style` y `::marker` computan `none` en las
  cuatro listas, con una sola numeración a 375×812 y 1280×900 y sin desborde horizontal. La sonda
  inversa (forzar `list-style: decimal`) confirma que la regla publicada es la que suprime el
  marcador.
- Suites compartidas de chat, cierre de turno y traducción: 50 passed; flags de aislamiento,
  presupuesto de tiempo, directorio temporal y cancelación sin cambios de comportamiento.

T5 cumplió sus tres frentes (checks, verificación funcional y documentación), así que F5 queda
cerrada con estos límites explícitos: la carrera al crear dos planes del mismo idioma sigue dando
500 en vez de 409 (L4), el frontend no tiene suite propia y todo el trabajo de F5 está sin commit.
El orquestador limpió la copia temporal; no se modificó la base de uso cotidiano ni se hizo push.

**L10 — commits y entrega, pedido literal:**

> vamos a subir todos los cambios al repo

Antes de escribir historia se revalidó el árbol completo: `uv run pytest` **203 passed**, `ruff
check` y `ruff format --check` limpios, `npm run typecheck` exit 0 y `npm run build` ✓.

Slices de la entrega (`chain_strategy=feature-branch-chain`, elegida por el humano):

| Slice | Commit | Contenido |
|---|---|---|
| 1 | `8ba8964` | PWA: catálogo, práctica/resultado, plan, tipos y rutas, tarjetas reales de inicio |
| 2 | `00d8dcb` | `OSError` del arranque de Pi → `LlmUnavailable`, con sus dos tests |
| 3 | este commit | README, roadmap, README del frontend y cierre de T4/T5 con sus hashes |

El slice 1 no se puede partir en lecciones y planes sin inventar estados intermedios: comparten
`App.tsx`, `types.ts`, `HomePage.tsx` y la eliminación de los placeholders, y un corte dejaría un
build roto. Se commitó como una unidad coherente de 2.466 líneas, por encima de la heurística de
400, sin recortar tests ni documentación para reducir el conteo.

Queda sin versionar `backend/package-lock.json` (un lockfile vacío generado por error fuera de
`frontend/`), ajeno a F5 y a la espera de que el humano decida borrarlo. `main` no se toca: el push
sube solo esta rama.
