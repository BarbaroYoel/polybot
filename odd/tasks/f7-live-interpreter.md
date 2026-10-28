# F7 — Intérprete en tiempo real

Fase F7 de `docs/roadmap.md`. **Estado: completada.** Rama `feat/f7-live-interpreter`, cortada de
`main` (`dba34b4`, PR #1 ya mergeado). Checks ejecutados: `uv run pytest`, `uv run ruff check`,
`uv run ruff format --check`, `npm run typecheck` y `npm run build`.

## Specs

**S1 — La pantalla `/translate` tiene dos modos separados.** Literal de `desing.md` §6.4:

> **Dos modos separados:**
> 1. **Traducir texto:** idioma origen/destino, entrada, traducción, copiar y reproducir audio.
> 2. **Intérprete de voz:** controles para iniciar / detener escucha; transcripción original y
>    traducción por segmentos; reproducción opcional del resultado.

Hoy `/translate` es un placeholder de F1 (`frontend/src/features/sections/pages.tsx`). El modo texto
reutiliza `POST /translate` (ADR-014); el modo intérprete es el trabajo nuevo de F7 y no comparte
estado con una lección ni con el chat.

**S2 — WebSocket, no SSE.** `docs/stack.md` ya decidió «SSE para el chat; WebSocket solo para el
intérprete» y `docs/api-contract.md` §3 ya reserva `WS /voice/interpret` con una línea sin detallar.
F7 define el protocolo y actualiza el contrato en el mismo cambio (AGENTS.md §6.4).

**S3 — STT en streaming con Whistle, en ventanas.** ADR-015 ya eligió el streaming nativo del motor
para el intérprete. La API instalada en esta máquina (`cactus-needle` 3.2.8) expone:

```
needle.stream(chunks, language=None, keywords=None, weights=None)
```

Recibe buffers de samples float de 16 kHz (≈1 s cada uno) y devuelve, por chunk, `text` confirmado,
`pending` sin confirmar, `language`, `received` y `pass_ms`; al terminar los chunks entrega la cola.
La firma se confirmó por inspección. T0 midió que un stream continuo se degrada después de ~5 s, así
que el intérprete lo reinicia en **ventanas de 4,5 s con 0,5 s de solape** (ADR-022); el detalle está
en «T0 — resultados». El adaptador sigue apagando `NEEDLE_TELEMETRY=0`, corre en un hilo de CPU y
**no escribe audio**.

**S4 — Traducción de parciales y segmentos finales con el mismo proveedor.** Decisión P5: también
se traduce el texto parcial, con *debounce* y descarte de respuestas viejas para que el texto no
salte. Cada actualización se traduce con `LlmPort.translate` y el prompt versionado `translate.v1`
(ADR-014); el segmento final se traduce una vez y reemplaza al parcial. Origen y destino salen de
los selectores de la pantalla, **nunca** del idioma activo global: el intérprete no es una
conversación de práctica. Un fallo del proveedor no borra el transcript original.

**S5 — Historial de fragmentos originales y traducidos, en orden temporal.** `desing.md:252`. La
lista vive en la sesión del intérprete y es **efímera** (P2): memoria de la pestaña, sin tabla ni
migración; al detener o recargar se pierde.

**S6 — Estados visibles y aviso de latencia.** `desing.md:251-255`: señal de micrófono activo,
estados sin permiso / conectado / escuchando / procesando / error / detenido, y una nota visible de
que la latencia y la precisión varían según el audio y la conexión. Nada de botones decorativos.

**S7 — Nada de audio persistido sin consentimiento.** AGENTS.md §3 y `desing.md:255`: la v0 no
graba ni conserva audio del usuario. El audio viaja por el WebSocket, se transcribe y se descarta.

**S8 — TTS fuera de F7 (decisión P4).** El audio de la traducción queda para otra fase: ni el modo
texto ni el intérprete muestran «Escuchar». `desing.md:247` lo marca opcional y §6.4 pide
«reproducir audio» en el modo texto; la diferencia se registra como límite explícito, no se
esconde con un botón decorativo (AGENTS.md §3).

**S9 — La UI no conoce el harness.** Habla HTTP y WebSocket con la API; no importa Pi, OpenCode ni
Whistle (ADR-004). El WebSocket debe funcionar por el proxy de Vite y por la URL de Codespaces.

**S10 — Dos idiomas, sin mezclar.** El intérprete traduce de un idioma de origen a uno de destino;
no escribe conversaciones, lecciones ni progreso del idioma activo. Un idioma no soportado por el
STT se informa como error accionable, no se adivina.

## Decisiones tomadas (2026-10-28)

| ID | Decisión |
|---|---|
| P1 | **El modo «Traducir texto» entra en F7** como primer corte (T4). |
| P2 | **Sesiones efímeras**: historial en memoria de la pestaña, sin tabla ni migración; al detener o recargar se pierde. |
| P3 | **Detección automática opcional** del origen («Detectar»); el destino siempre se elige a mano. |
| P4 | **TTS diferido**: la reproducción de la traducción queda fuera de F7 y no se muestra el control. |
| P5 | **Se traducen también los parciales**, con *debounce* y descarte de respuestas viejas. |
| P6 | **La traducción con OpenCode usa un agente propio** (`general` por defecto, `OPENCODE_TRANSLATION_AGENT`); el tutor conserva `plan`. |

## Contrato propuesto (borrador)

`WS /api/v1/voice/interpret?source=<code>&target=<code>`

- `source` es opcional: sin él se pide detección automática (P3). `target` es obligatorio.
- Al abrir, el servidor responde:

```jsonc
{ "type": "ready", "format": "pcm_s16le", "sample_rate": 16000,
  "source": "fr", "target": "es" }
```

- Cliente → servidor:
  - **Frames binarios**: PCM mono 16 bits little-endian a 16 kHz, en trozos de 0,25–1 s. Sin
    cabecera WAV; el servidor valida el tamaño y descarta el resto.
  - `{"type":"stop"}`: cierra la entrada, vacía la cola del motor y espera el último segmento y su
    traducción antes de cerrar.
  - `{"type":"cancel"}`: descarta parciales y cierra sin traducir.
- Servidor → cliente:
  - `{"type":"partial","seq":12,"text":"...","pending":"...","language":"fr","received_ms":1200}`
  - `{"type":"partial_translation","seq":12,"text":"...","target":"es"}` — efímera, no entra al
    historial.
  - `{"type":"segment","id":"...","text":"...","language":"fr","start_ms":0,"end_ms":2400}`
  - `{"type":"translation","segment_id":"...","text":"...","target":"es"}`
  - `{"type":"error","error":{"code":"...","message":"...","details":{},"request_id":"..."}}`
- Orden: los `partial` y `partial_translation` se intercalan por `seq`; solo los `segment`
  confirmados pasan al historial. Una traducción final nunca llega antes de su segmento.
- **Ventanas:** el servidor reinicia el motor cada 4,5 s y arrastra 0,5 s de solape; el texto del
  borde se deduplica antes de emitir el `segment`. Un `segment` representa una ventana, no una frase.
- Parciales: *debounce* de ~400 ms desde el último cambio; una sola traducción en vuelo; una
  respuesta con `seq` viejo se descarta en el servidor y en el cliente. El segmento final traduce
  una vez y reemplaza al parcial.
- Límites propuestos: sesión de hasta 30 min y 60 s de silencio sin audio; audio inválido cierra con
  `1003`, parámetros inválidos con `1008`, fallo del motor o del proveedor con `1011`. Los errores
  usan el sobre del contrato §4 (`stt_unavailable`, `llm_unavailable`, `llm_timeout`).

## T0 — resultados (gate)

Clip: `jfk.wav`, 11 s de voz humana, 16 kHz mono 16 bits. `cactus-needle` 3.2.8,
`NEEDLE_TELEMETRY=0`. La máquina es un Codespace de 2 vCPU; durante la medición otro proceso
(HyperFrames) mantuvo la carga media alrededor de 5, así que los valores absolutos son pesimistas y
variables. Lo que se repitió en todas las corridas es la forma del coste.

| Prueba | Resultado observado |
|---|---|
| Warm-up en frío (carga del motor incluida) | 4,1 s |
| `transcribe` del clip completo (11 s) | 4,8–5,9 s (0,44–0,54× tiempo real) |
| `transcribe` de ventanas de 4–5 s | 0,3–1,3 s por ventana (4–16× tiempo real) |
| `stream` continuo, chunks de 1 s, 11 s | 26,2 s (2,4× tiempo real); primer parcial a 104 ms |
| `stream` continuo, chunks de 0,5 s, 11 s | 50,1 s (4,6× tiempo real) |
| `stream` continuo, chunks de 0,25 s, 11 s | 114,7 s (10,4× tiempo real) |
| `stream` continuo, 22 s, chunks de 1 s | 84,2 s (3,8× tiempo real) |
| `stream` con reset cada 4 s, 22 s | 4,8 s (0,22× tiempo real; 4,6× más rápido) |
| `stream` con reset cada 4,5 s, 22 s | 7,2 s (0,33×; una ventana aislada de 2,7 s) |
| `stream` con reset cada 5 s, 22 s | 9,0 s (0,41×) |
| `stream` con reset cada 4,5 s bajo carga | 22,0 s (1,0×): la CPU compartida se come el margen |
| Silencio de 2 s | 3 yields, texto vacío, 4 ms |
| Detección de idioma | `en` correcto; el batch devolvió el texto exacto |
| `pass_ms` | Es acumulado por stream y se reinicia al cerrar un segmento: no sirve como latencia por chunk |

**Conclusión.** Un `needle.stream` continuo no es viable: el coste crece con la longitud y supera el
tiempo real. Reiniciar el stream cada ≤5 s sí es viable; la ventana de 4,5 s deja margen y el primer
parcial llega con el primer chunk. El intérprete usará **ventanas de 4,5 s con reset, solape de
0,5 s y deduplicación en el borde** (ADR-022). La traducción de parciales (P5) se mantiene, con
debounce y una sola petición en vuelo. La CPU compartida puede atrasar la sesión: la UI debe mostrar
el estado y no prometer una latencia fija.

## Tasks

| ID | Specs | Ruta y alcance | Estado |
|---|---|---|---|
| T0 | S3 | Verificar `needle.stream` con audio real: tamaños de chunk, latencia del primer parcial, cola final, detección de idioma y comparación con `transcribe`. **Gate**: si no es viable, se detiene y se reporta. | completada; ver «T0 — resultados» |
| T1 | S2, S6, S10 | Backend: endpoint WS, modelos del protocolo, máquina de estados, mapeo de errores y tests con un `STT` falso; contrato actualizado. | completada; 6 tests de integración |
| T2 | S3, S7 | Adaptador de streaming: extensión del puerto `STT`, puente hilo→asyncio, **ventanas de 4,5 s con reset y 0,5 s de solape**, deduplicación en el borde, telemetría apagada y tests con `needle` falso. | completada; 3 tests del adaptador |
| T3 | S4, S6 | Traducción de parciales y segmentos finales: *debounce*, una sola petición en vuelo, descarte por `seq`, orden, timeout y tests con `LLM` falso. | completada; tests de sesión |
| T4 | S1, P1 | PWA modo texto: `/translate` con selectores, entrada, resultado y copiar; reutiliza `lib/api/translate.ts`. Sin «Escuchar» (P4). | completada; probada en navegador |
| T5 | S1, S5, S6, S9, P2, P3, P5 | PWA intérprete: captura continua, cliente WS, transcript en vivo con parciales traducidos, historial efímero, estados y aviso de latencia. | completada; probada en navegador con micrófono falso |
| T6 | todas | Verificación de punta a punta con audio real, sonda de navegador, tabla de latencias, ADR-022 con P1–P5, roadmap y límites. | completada; ver «T6 — resultados» |

## Verificación prevista

- Suite backend completa en verde y tests nuevos para el protocolo, el adaptador y la traducción;
  `ruff format --check` y `ruff check` limpios.
- `npm run typecheck` y `npm run build` verdes.
- T0 con un clip real: tabla de latencia por tamaño de chunk y texto devuelto, sin tocar el motor
  desde la suite.
- Punta a punta real en dos direcciones (p. ej. `fr→es` y `en→de`): parciales, traducciones de
  parciales, segmentos finales y traducciones finales en orden; una respuesta vieja no pisa a la
  nueva; `stop` entrega la cola; `cancel` no traduce nada.
- Sonda de navegador a 1280×900 y 375×812: micrófono, estados, historial, sin desborde horizontal;
  permiso denegado y caída de red con mensajes accionables.
- WebSocket a través del proxy de Vite (`ws: true`) y de la URL de Codespaces.
- Confirmar que no se escribe audio ni se crean filas: P2 es efímera.
- Modo texto: traducir, copiar y estados de error; sin botón de audio (P4).

## T6 — resultados (2026-10-28)

**Backend.** `uv run pytest` → **292 passed in 44.44s**; `ruff check` y `ruff format --check`
limpios. **Frontend:** `npm run typecheck` y `npm run build` verdes.

**Intérprete real.** Base SQLite aislada, migrada y sembrada, `uvicorn` en el puerto 8010, Whistle
real y OpenCode real (`opencode-go/deepseek-v4.1-flash`). Clip humano de 11 s (`jfk.wav`) enviado
como PCM s16le de 16 kHz:

| Evento | Primer timestamp | Contenido |
|---|---|---|
| `partial` | 0,8 s | «And…» |
| `segment` 1 | 2,0 s | «And so my fellow Americans ask not.» `[0–4500]` |
| `segment` 2 | 3,3 s | «what your country can do for you.» `[4000–8500]` |
| `segment` 3 | 3,9 s | «ask what you can do for your country.» `[8000–11000]` |
| `translation` 1 | 7,3 s | «Y así, mis conciudadanos estadounidenses, no pregunten.» |
| `translation` 2 | 9,8 s | «lo que tu país puede hacer por ti.» |
| `translation` 3 | 12,2 s | «pregunta qué puedes hacer por tu país.» |

Total: 12,2 s para 11 s de audio. El cuello es el proveedor de traducción, no el STT (los segmentos
llegan a 2–4 s).

**Agente de traducción.** Con `OPENCODE_AGENT=plan`, el modelo narraba su propio rol y devolvía
comentarios meta (71–98 s y texto sobre el prompt o el repo). Se agregó
`OPENCODE_TRANSLATION_AGENT=general` (default) para la traducción; el tutor sigue con `plan`. La
corrida de la tabla usa `general` y las tres traducciones salieron limpias. Una instalación sin
`general` puede volver a `plan` por configuración.

**Parciales.** El mecanismo de traducción de parciales está implementado y probado con un LLM falso.
Con el proveedor actual (3–7 s por traducción), el parcial suele quedar viejo cuando la ventana de
4,5 s ya cerró y se descarta; en la práctica la UI muestra la traducción final. Si el proveedor es
más rápido, los parciales aparecen. No se bloquea el STT por esperar una traducción.

**PWA.** Chromium headless (Playwright) con micrófono falso (`jfk.wav`), a 1280×900 y 375×812:

- Modo texto: «How are you?» → «¿Cómo estás?»; sin errores de consola; `scrollWidth == innerWidth`
  (sin desborde).
- Intérprete: estados, tres segmentos y sus traducciones tras «Detener»; sin errores de consola;
  sin desborde.
- Capturas en `/tmp/opencode/f7-t6/translate-text.png`, `translate-interpreter.png`,
  `translate-text-mobile.png` y `translate-interpreter-mobile.png`.
- Observación fuera de F7: a 375 px el saludo del TopBar se parte en cuatro líneas; no hay desborde,
  pero conviene acortarlo u ocultarlo en esa medida.

## Riesgos y límites conocidos

- **Latencia del proveedor.** Medido en T6: 3–7 s por traducción y 12,2 s para los 11 s de audio.
  La UI muestra «Procesando…»/«Traduciendo…» y no finge tiempo real. Con OpenCode, la traducción
  usa `general`; `plan` narraba su rol y devolvía comentarios meta.
- **Costo de traducir parciales (P5).** Multiplica las llamadas al proveedor y el texto puede
  cambiar mientras se lee. Con el proveedor actual, el parcial suele quedar viejo cuando la ventana
  de 4,5 s cierra y se descarta; la traducción final manda. Mitigación: *debounce* de ~600 ms, una
  sola petición en vuelo y descarte por `seq`; si el proveedor es más rápido, se ven los parciales.
- **Corte de 5 s del motor.** Un `needle.stream` continuo se degrada después de ~5 s (T0): 22 s de
  audio tardaron 84 s. El intérprete reinicia el motor cada 4,5 s (ADR-022); el corte puede partir
  una frase y el borde se deduplica. No es un stream continuo de toda la sesión.
- **CPU compartida.** La máquina tiene 2 vCPU y durante T0 otro proceso la ocupó: una ventana de
  4,5 s tardó entre 0,9 s y 4,4 s. Si el motor no da abasto, la sesión se atrasa; la UI debe mostrar
  «Procesando…» y no prometer latencia fija.
- **Motor STT.** La primera llamada de un proceso paga ~4–9 s de carga; el warm-up sigue pendiente
  de F4. T0 midió el motor real con un clip humano, pero no con voz de los siete idiomas.
- **Captura del navegador.** `recorder.ts` usa `ScriptProcessorNode` (deprecado, sin build extra).
  Para streaming hay que enviar chunks sin cortar la grabación; `AudioWorklet` exigiría un módulo y
  un paso de build que el stack no decidió.
- **WebSocket y proxies.** Vite necesita `ws: true` en el proxy `/api`; Codespaces debe mantener el
  puerto. Sin eso, el intérprete funciona en local y falla en la URL pública.
- **Persistencia efímera (P2).** Al detener o recargar se pierde el historial; es deliberado. Si más
  adelante se persiste, hará falta una tabla y una decisión de privacidad sobre texto y audio.
- **TTS diferido (P4).** `desing.md` §6.4 pide reproducción de audio en el modo texto y la marca
  opcional en el intérprete; no se muestra el control hasta que exista. Queda como pendiente.
- **Tests de frontend.** Sigue sin suite propia porque el stack de testing no está decidido
  (`docs/stack.md`); la verificación es manual y con sonda de navegador.
- **TopBar a 375 px.** El saludo se parte en cuatro líneas; no hay desborde horizontal, pero es una
  deuda visual de la carcasa (F1), fuera del alcance de F7.
- **Sin auth.** La API no debe exponerse públicamente (ADR-012); el intérprete hereda esa regla.

## Log

**L1 — planificación.** El humano pidió «vamos con 1 y luego con la dos»: primero el PR de F6
(mergeado como PR #1, `main` en `dba34b4`) y después el plan de F7. Se corta
`feat/f7-live-interpreter` desde `main` y se escribe este documento. El plan queda sin commit
hasta el cierre de la fase.

**L2 — decisiones P1–P5 confirmadas por el humano (2026-10-28).** Modo texto incluido en F7;
sesiones efímeras sin tabla; «Detectar» como origen opcional; TTS diferido y fuera de la pantalla;
traducción de parciales además de los finales. El plan y el contrato propuesto quedan actualizados.

**L3 — T0 ejecutado (2026-10-28).** Clip humano de 11 s (`jfk.wav`, 16 kHz mono) contra
`cactus-needle` 3.2.8. El stream continuo no es viable: 26 s para 11 s con chunks de 1 s y 84 s para
22 s; el coste crece con la longitud. Las ventanas con reset cada 4,5 s vuelven a 0,9–4,4 s por
ventana. Se registra **ADR-022** y se ajusta el plan: ventanas de 4,5 s con 0,5 s de solape y
deduplicación. La carga de CPU de la máquina (2 vCPU, otro proceso activo) hace que los valores
absolutos varíen; la discontinuidad de ~5 s se repitió. La sonda vive en `/tmp/opencode/f7-t0/` y no
entra al repo.

**L4 — T1–T3 implementados y en verde (2026-10-28).**

- `backend/app/ports/stt.py`: `StreamUpdate` + `SttPort.stream`.
- `backend/app/adapters/stt/whistle.py`: puente hilo→asyncio; telemetría apagada antes del import;
  el motor corre en un worker; sin archivos.
- `backend/app/application/interpreter.py`: sesión efímera, ventanas de 4,5 s, solape de 0,5 s,
  deduplicación, parciales + traducción con debounce, traducción final autoritativa, errores.
- `backend/app/api/v1/voice.py`: `WS /voice/interpret` con PCM s16le, `stop`/`cancel`, códigos de
  cierre y el sobre de error del contrato.
- `backend/app/core/dependencies.py`: dependencias WS (`get_ws_stt`, `get_ws_llm`,
  `get_ws_interpreter_service`).
- Tests: `test_whistle_adapter.py` (3 de streaming), `test_interpreter_session.py` (9) y
  `test_interpreter_api.py` (6).
- `uv run pytest` → **291 passed in 32.77s**; `ruff check` y `ruff format --check` limpios.
- `docs/api-contract.md` documenta `WS /voice/interpret`; `docs/decisions.md` ADR-022;
  `docs/stack.md` fija WebSocket + ventanas.

Quedan T4 (modo texto), T5 (PWA del intérprete) y T6 (verificación de punta a punta con audio real
y sonda de navegador); el commit de cierre se hace en L6.

**L5 — T4–T6 completados (2026-10-28).** Se implementaron el modo texto y el intérprete de la PWA
(`frontend/src/features/translate/`), el cliente WebSocket (`lib/api/interpreter.ts`), la captura
continua sobre `VoiceRecorder` y el hook `useInterpreter`. El proxy de Vite gana `ws: true`.

La prueba real destapó que el agente `plan` de OpenCode narraba su rol en la traducción
(71–98 s y comentarios meta). Se agregó `OPENCODE_TRANSLATION_AGENT` (default `general`) y se usa
solo en `translate()`; el tutor conserva `plan`. Ver «T6 — resultados».

`uv run pytest` → **292 passed in 44.44s**; Ruff limpio; `npm run typecheck` y `npm run build`
verdes; sonda de navegador a 1280×900 y 375×812 sin errores de consola ni desborde. El commit de
cierre se hace en L6.

**L6 — commit de cierre (2026-10-28).** El humano pidió «comitea». Se commitea F7 completo en
`feat/f7-live-interpreter`; el backup local `backend/polybot.db.bak-2026-10-26` queda fuera por ser
dato de la base. No se hace push ni PR en este paso.
