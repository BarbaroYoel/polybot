# Inicio separado del chat + corrección del solapamiento

Cambio de UI posterior a F1. Autorizado por el humano en L1/L2. Rama: `feat/f1-pwa-shell`.
Sin commits: AGENTS.md §6.7 exige pedido explícito y no lo hubo.

## Specs

**S1 — El chat no se pinta sobre otros textos.** L1: «la parte del chat aparece encima de unos textos y no se logra difewrwnciar». Cada bloque de la pantalla de conversación ocupa su propia fila: nada de mensajes sobre avisos, nada de contenido fuera del viewport.

**S2 — Las tarjetas de resumen van a otra pantalla.** L1: «quiero que esto Lección de hoy / Vocabulario en situaciones cotidianas / Continuar / Meta semanal / 4 de 7 conversaciones / Próxima práctica / Hoy, 17:00 · Conversación: en un café este con otra pantalla no encima del chat».

**S3 — Esa otra pantalla es un inicio con historial.** L2: «Inicio con historial de conversaciones». `/` muestra las tres tarjetas y la lista de conversaciones del idioma activo; `/chat/:conversationId` es la conversación, sin tarjetas.

**S4 — `desing.md` y ADR.** L2: «Actualizar desing.md + ADR». Se ajustan §4 (rutas), §5 (wireframe y medidas), §6.1 (pantalla) y §9 (móvil); se registra ADR-011 en `docs/decisions.md`.

**S5 — Los textos de las tarjetas no cambian.** Se conservan literales: `Lección de hoy` · `Vocabulario en situaciones cotidianas` · `Continuar` · `Meta semanal` · `4 de 7 conversaciones` · `Próxima práctica` · `Hoy, 17:00 · Conversación: en un café`.

## Tasks

| ID | Qué | Specs | Estado | Commit |
|---|---|---|---|---|
| T1 | Pantalla de inicio `/` con las tres tarjetas, aviso de datos de ejemplo e índice de conversaciones del idioma activo | S2, S3, S5 | hecho | — |
| T2 | Rutas: `/` inicio, `/chat/:conversationId` conversación; `/chat` redirige a `/`; sidebar activo dentro de una conversación | S3 | hecho (la parte del sidebar se completó al retomar, L6) | — |
| T3 | Pantalla de conversación sin tarjetas y con la grilla corregida (filas explícitas, columnas `minmax(0, 1fr)`, scroll propio, compositor siempre visible); conversación inexistente con recuperación | S1 | hecho (incluye los defectos preexistentes de L7) | — |
| T4 | Documentación: `desing.md` §4/§5/§6.1/§9, ADR-011, roadmap F1, evidencia y `docs/architecture.md` | S4 | hecho (completado al retomar, L6) | — |
| T5 | Verificación: typecheck, build, geometría en 8 viewports y capturas | S1–S5 | hecho (completado al retomar, L5 y §Verificación) | — |

## Log

**L1** — Pedido original, literal:

> la parte del chat aparece encima de unos textos y no se logra difewrwnciar , quiero que esto Lección de hoy
> Vocabulario en situaciones cotidianas
>
> Continuar
> Meta semanal
> 4 de 7 conversaciones
>
> Próxima práctica
> Hoy, 17:00 · Conversación: en un café este con otra pantalla no encima del chat

**L2** — Respuestas a las dos preguntas bloqueantes: «Inicio con historial de conversaciones» y «Actualizar desing.md + ADR».

**L3** — Causa del defecto, observada antes de escribir código: `ChatPage` renderiza 4 hijos (tarjetas, aviso, hilo, compositor) en una grilla de 3 filas (`chat.css:1-7`). La fila `minmax(0, 1fr)` cae sobre el aviso y `.chat__scroll` queda en fila `auto`, así que el hilo toma alto de contenido, desborda la grilla y se dibuja encima del aviso; con ventanas bajas el compositor queda empujado fuera del área. Captura en `1366×768` con el aviso cortado por el primer mensaje.

**L4** — Sin test runner en `frontend/` (no hay script `test` ni framework instalado) y AGENTS.md §5 prohíbe instalar por iniciativa propia: la verificación de T5 es typecheck + build + sonda de geometría en Chrome headless + capturas, no RED/GREEN.

**L5** — Sesión retomada con el mismo pedido. Evidencia del defecto original en el commit base `baf3c21`
(worktree en `/tmp/polybot-base`): la captura a 1366×768 muestra el hilo pintado **encima** del aviso de datos de
ejemplo y de las tarjetas. En el árbol de trabajo la sonda no encuentra ningún elemento tapado ni contenido fuera
del viewport en 1440×900, 1366×768, 1280×600, 1280×480, 820×1180, 768×1024 y 390×844, para `/`, `/chat/c-fr-1`,
`/chat/c-en-1` y `/chat/no-existe`. El defecto reportado está corregido.

**L6** — Reconciliación al retomar: T4 y T5 figuraban como «hecho» sin ningún cambio en `desing.md`,
`docs/decisions.md`, `docs/roadmap.md` ni `docs/architecture.md`, y sin verificación registrada. Se completaron en
esta sesión. T2 tampoco estaba completa: `Sidebar.tsx` usaba `end: true` en el ítem «Conversaciones», así que con
`/chat/:id` ya no quedaba marcado como activo. Se corrigió con `alsoActiveOn` y se verificó que haya exactamente un
ítem activo y con `aria-current="page"` en `/`, `/chat/c-fr-1`, `/chat/c-en-1`, `/lessons`, `/progress` y
`/settings`.

**L7** — Defectos de layout **preexistentes de F1** que aparecían en la misma pantalla y se corrigieron acá. Todos
se midieron también en `baf3c21`, así que no los introduce la separación inicio / conversación:

1. `.chat` y `.shell__main` no declaraban columna de grilla, así que la columna implícita `auto` crecía por encima
del contenedor y `.shell__content` (`overflow: hidden`) la recortaba en silencio. A 390px `.chat__scroll` medía
447px: el hilo se cortaba a la derecha y parecía texto encimado, sin scroll horizontal que lo salvara. Se agregó
`grid-template-columns: minmax(0, 1fr)` en ambos contenedores y `min-width: 0` en `.chat__scroll`,
`.chat__composer-wrap` y `.composer__input`.
2. `.topbar__title` recortaba palabras largas a 360px (104px de contenido en una caja de 87px). Se agregó
`overflow-wrap: break-word`.

Con eso la sonda no encuentra ningún elemento más ancho que su padre, ningún texto recortado y ningún desborde
horizontal en 320, 360, 390, 420 y 768 de ancho, para `/`, `/chat/:id`, `/lessons`, `/settings` y `/translate`.
El follow-up FU-1 que había quedado abierto se corrigió con el punto 1.

## Verificación

Comandos, todos ejecutados sobre el árbol de trabajo:

| Qué | Comando | Resultado |
|---|---|---|
| Typecheck | `npm run typecheck` (en `frontend/`) | sin errores |
| Build | `npm run build` (en `frontend/`) | `✓ built in 670ms`, 61 módulos |
| Geometría | sonda CDP propia sobre Chrome headless: `elementFromPoint` sobre aviso, tarjetas, burbujas y compositor; contención en viewport; desborde horizontal | 0 problemas en 8 viewports × 4 rutas |
| Recorte móvil | sonda de elementos más anchos que su padre y de texto recortado | 0 problemas en 5 anchos × 5 rutas |
| Navegación | sonda CDP de `sidebar__link--active` y `aria-current` | 6/6 rutas correctas |

Viewports de la sonda de geometría: 1440×900, 1366×768, 1280×600, 1280×480, 820×1180, 768×1024, 390×844 y 360×640.
Rutas: `/`, `/chat/c-fr-1`, `/chat/c-en-1`, `/chat/no-existe`.
La sonda comprueba, con `elementFromPoint`, que ningún elemento tape un aviso, una tarjeta, una burbuja o el
compositor; que aviso, tarjetas, historial y compositor queden dentro del viewport; y el desborde horizontal del
documento.
