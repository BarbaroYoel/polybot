# F4 — Voz

Fase F4 de `docs/roadmap.md`. Autorizada en L1: el humano pidió «vamos con eso» (F4) y confirmó el
modelo STT para esta fase. Arranca **después** de `odd/tasks/message-translation.md`, ya completada.
Sin commits: `AGENTS.md` §6.7 lo prohíbe salvo pedido explícito.

## Specs

**S1 — STT con Whistle, local, detrás de un puerto.** Literal del humano:
«vamos con eso y esto https://huggingface.co/Cactus-Compute/whistle para el stt». Whistle (Cactus
Compute) corre en el backend por CPU a través de `cactus-needle`, con streaming nativo y siete idiomas
(inglés, alemán, francés, español, italiano, neerlandés, polaco). Vive detrás de un puerto `STT` con
adaptador reemplazable, igual que `LLM` (ADR-004, ADR-015). El audio no sale de la máquina.

**S2 — Antes de escribir el adaptador, Whistle tiene que correr en esta máquina.** `docs/stack.md`
prohíbe promover una propuesta sin confirmar: la primera tarea es instalar `cactus-needle` en un
entorno descartable, transcribir un clip real y medir latencia. Si no corre acá, la fase se detiene y
la decisión vuelve al humano con la evidencia (ADR-015).

**S3 — `POST /voice/transcribe` según el contrato.** `multipart/form-data` (`audio`, `language_code?`)
→ `{ "text", "language_detected", "duration_ms" }`, con el sobre de error del contrato §4: un cuerpo
sin `audio` o con un `audio` vacío es 422 `validation_error` —es error de esquema, como el resto de la API—;
audio corrupto o de formato no soportado, 400 `invalid_audio`; más de 120 s, 413 `audio_too_long`; fallo del
motor, 502 `stt_unavailable`. Un audio sin voz devuelve texto vacío, no una frase inventada
(`docs/api-contract.md` §3 «Voz»).

**S4 — TTS con Piper, ya decidido en ADR-003.** `POST /voice/speech` (`text`, `language_code`,
`voice?`, `speed?`) → audio, con síntesis local y caché en `GET /voice/speech/{id}`. El streaming por
frases es el objetivo de la fase; la primera entrega puede sintetizar el mensaje completo y el
streaming de frases se verifica aparte.

**S5 — Estados visibles, sin decoración.** `desing.md` §6.1.2 y §8: «Escuchando…», «Transcribiendo…»,
«Pensando…», «Reproduciendo…» siempre visibles según el flujo real; el permiso de micrófono se pide
cuando corresponde y su denegación tiene estado propio con acción de recuperación. Ningún botón de
audio se muestra si no hace algo (hoy «Escuchar» y «Más lento» están deshabilitados y dicen por qué).

**S6 — El texto transcripto se edita antes de enviar.** `docs/roadmap.md` F4: el transcripto deja de
ser audio y pasa al compositor, donde el usuario lo corrige o lo descarta. Enviar voz nunca saltea la
posibilidad de leer y editar el texto.

**S7 — Nada de audio persistido sin consentimiento.** AGENTS.md §3 y `desing.md` §6.4: no se guarda
audio sin consentimiento explícito y control visible. La v0 transcribe y descarta el archivo.

## Tasks

| ID | Specs | Ruta | Commit |
|---|---|---|---|
| T1 | S2 | Verificar `cactus-needle` en esta máquina con un clip real: instalar en un entorno descartable, transcribir, medir latencia | sin commit |
| T2 | S1, S3 | Puerto `STT` + adaptador Whistle + `POST /voice/transcribe`, con tests sobre un doble del motor | sin commit |
| T3 | S5, S6 | Frontend: micrófono (permiso + estados), envío del audio, transcripto editable en el compositor | sin commit |
| T4 | S4 | Puerto `TTS` + adaptador Piper + `POST /voice/speech` y `GET /voice/speech/{id}` con caché | sin commit |
| T5 | S5 | Reproducción en el chat: «Escuchar», «Más lento» y el estado «Reproduciendo…» dejan de estar deshabilitados | sin commit |
| T6 | todas | Checks de la fase y verificación de un turno de voz completo con latencia medida | — |

## Log

**L1 — pedido original, literal:**

> perfecto vamos con eso y esto https://huggingface.co/Cactus-Compute/whistle para el stt pero antes
> vamos a habilitar las traducciones de las respuestas , incluso quisiera que puesda seleccionar una
> parte del texto y que eso sea lo que se tradusca , para que no sea completo

**L2 — la decisión del modelo quedó registrada como ADR-015** (`docs/decisions.md`): Whistle local por
CPU vía `cactus-needle`, siete idiomas, streaming. Q4 de `docs/open-questions.md` queda resuelta y la
fila de `docs/stack.md` pasa a «Decidido».

## Verificación de T1 — Whistle en esta máquina

Entorno descartable `data/whistle-venv` (no toca `pyproject.toml` ni el lock), clip de 2,97 s generado
con `ffmpeg` + `flite` y texto conocido: «the quick brown fox jumps over the lazy dog».

| Qué | Resultado observado |
|---|---|
| Instalación | `cactus-needle` **3.2.8** desde PyPI, sin compilar, en ~10 s |
| Firma real | `needle.transcribe(audio, language=None, keywords=None, word_timestamps=False, weights=None) -> dict` |
| Primera llamada (carga del motor incluida) | 8,717 s |
| Segunda llamada (caché caliente) | **0,413 s** para 2,97 s de audio |
| Detección automática de idioma | 0,642 s, `language: "en"` |
| Texto devuelto | «The quick brown fox jumped over the lazy dog.» — un error de concordancia (`jumps` → `jumped`), el resto correcto |
| Métricas del motor | `ttft_ms` 70-146 ms, `decode_tps` 28-236 |

**Hallazgo que cambia una afirmación:** el paquete escribe en su salida que **recolecta conteos de uso
anónimos** (función, versión, SO; no prompts ni audio) y que se desactiva con `NEEDLE_TELEMETRY=0`. El
audio no sale de la máquina, pero el contador sí: el adaptador debe fijar `NEEDLE_TELEMETRY=0` antes de
importar `needle`, y ADR-015 lo registra.

**Descartado:** el intento anterior generó clips con el filtro `flite` de `ffmpeg` (solo voces en inglés)
nombrados `clip_es`/`clip_fr`; esa medición habría mentido sobre los idiomas. Los clips engañosos y los
scripts del intento fallido se borraron.

**T2 — STT detrás del puerto, implementado y en verde.** `SttPort` + `Transcription` en
`ports/stt.py`, adaptador Whistle en `adapters/stt/whistle.py`, `VoiceService` en `application/voice.py`
y `POST /voice/transcribe` (`multipart/form-data`, `audio` + `language_code?`) en `api/v1/voice.py`, con
los errores `invalid_audio` 400, `audio_too_long` 413 y `stt_unavailable` 502. El adaptador valida el WAV
con el módulo `wave` antes de tocar el motor (16 kHz mono 16 bits, 120 s), calcula `duration_ms` de los
frames, corre el motor en `asyncio.to_thread`, apaga la telemetría antes de importar `needle` (import
lazy) y le pasa muestras `float` en memoria: no escribe ningún archivo temporal. Tests: **33 nuevos**
(21 unit del adaptador sobre un `needle` falso en `sys.modules`, 12 de integración del endpoint), total
**156 en verde** con `uv run pytest -q`; `ruff format --check` y `ruff check` limpios. Contrato §1, §3
(«La transcripción»), §4 y §5 actualizados. Dependencia nueva no prevista en el brief:
`python-multipart`, que FastAPI exige para `multipart/form-data` (el contrato §3 ya pide multipart).

### Humo multilingüe

Clips sintéticos con `libespeak-ng` (voz robótica, vía `ctypes` porque el binario no está instalado),
convertidos a 16 kHz mono con `ffmpeg`:

| Clip | Idioma forzado | Tiempo | Texto devuelto | Idioma detectado |
|---|---|---|---|---|
| español, 3,00 s | `es` | 2,72 s (primer proceso) | «Buenos días, como estas hoy.» | `es` |
| español, 3,00 s | detección | 0,69 s | «Buenos días, como estas hoy.» | `es` |
| francés, 3,11 s | `fr` | 0,14 s | «Bonjour, comment allez-vous en jour libre ?» | `fr` |
| francés, 3,11 s | detección | 0,32 s | «Bonjour, comment allez-vous en jour libre ?» | `fr` |

Los acentos y la puntuación se normalizan (esperable) y hay un error real con la voz robótica
(«aujourd'hui» → «en jour libre»). Con voz humana habrá que volver a medir: esto prueba el runtime y los
idiomas, **no** la calidad.

**Límite de entrada confirmado:** el motor **rechaza** audio que no sea 16 kHz
(`RuntimeError: resampling 22050 Hz audio to 16000 Hz needs soxr: pip install "cactus-needle[mic]"`).
No se agrega el extra `[mic]`: el borde exige 16 kHz mono WAV y lo demás es `invalid_audio`.

**A verificar en T2/T6:** en un proceso nuevo el motor vuelve a hablar con Hugging Face («unauthenticated
requests to the HF Hub»). Hay que probar una transcripción con la red cortada y el caché caliente antes de
prometer que la voz funciona sin conexión.

**L3 — T2 implementado, verificado contra el motor real y contra la red cortada.**

El adaptador (`backend/app/adapters/stt/whistle.py`) valida el WAV con la stdlib *antes* de tocar el motor,
convierte el PCM a samples float **en memoria** (ningún archivo temporal: S7), corre el motor bloqueante en
`asyncio.to_thread` y fija `NEEDLE_TELEMETRY=0` antes del `import needle` perezoso.

| Verificación | Resultado |
|---|---|
| `uv run pytest` | **156 passed** (123 previos + 33 nuevos: 21 unitarios + 12 de integración) |
| `ruff format --check` / `ruff check` | limpios |
| Dependencias | `cactus-needle>=3.2.8` y `python-multipart>=0.0.32` (lo exige FastAPI para multipart); `uv.lock` sin líneas removidas |
| Motor **real** a través del adaptador | inglés «The quick brown fox jumped over the lazy dog.»; español «Buenos días, como estas hoy.»; francés «Bonjour, comment allez-vous en jour libre ?»; `duration_ms` 2965/2998/3113 |
| Latencia real | 7,43 s la primera llamada del proceso; después 0,069-0,193 s |
| Red cortada (`HF_HUB_OFFLINE=1`, caché caliente) | transcribe en 0,09-0,19 s: **no necesita red** una vez cacheado |
| Telemetría | no apareció el aviso de conteos: `NEEDLE_TELEMETRY=0` hace efecto |
| Mutaciones del worker | quitar `to_thread` y poner `import needle` arriba rompen sus tests |

**Desvío aceptado (cambio de spec, no del contrato):** subir un `audio` vacío devuelve 422, no 400. El
worker lo argumentó y el contrato quedó reescrito de forma coherente (§3 y §4 distinguen esquema de
contenido); S3 se corrigió arriba. Un audio **corrupto** sigue siendo 400.

**Límites que quedan anotados para T6:** el endpoint lee el cuerpo completo en memoria (sin tope de tamaño
previo); un código de idioma fuera de los siete de Whistle se reenvía tal cual (pregunta abierta, no error
inventado); la primera llamada de un proceso paga ~7-9 s de carga del motor, sin warm-up todavía.

**L4 — T3 (micrófono) implementado y verificado en navegador real.**

`frontend/src/lib/audio/recorder.ts` (getUserMedia + `AudioContext`, remuestreo a 16 kHz y codificación
WAV mono 16 bits, sin dependencias nuevas), `frontend/src/lib/api/voice.ts`,
`frontend/src/features/chat/useVoiceInput.ts` y el compositor con sus estados. `ChatPage` le pasa el
código del idioma de la conversación, así el motor no tiene que adivinar (S3).

Sonda propia en Chrome headless con dispositivo de audio falso, **tres navegadores limpios** (el primer
intento mezcló el stub de A con B y daba un falso verde: se descartó y se repitió):

| Escenario | Resultado observado |
|---|---|
| A — UI con la API simulada | click en el micrófono → «Escuchando…» → «Detener y transcribir» → el compositor queda con «Bonjour, je voudrais un café.», **nada se envía solo**, una sola petición, el estado desaparece |
| B — API **real** (Whistle real) | el WAV que graba el navegador vuelve 200 con `{"text":"Merci.","language_detected":"fr","duration_ms":1536}` (el clip es un tono del dispositivo falso: 1,54 s de audio, duración correcta) |
| C — permiso denegado | «No tenemos permiso para usar el micrófono. Revisá los permisos del navegador para este sitio.» y **cero** peticiones |

`npm run typecheck` y `npm run build` verdes. Límites conocidos: la grabación usa `ScriptProcessorNode`
(deprecado pero sin build extra) y el clip se corta a los 2 minutos avisando por qué.

**L5 — T4 y T5 (audio de salida) implementados y verificados.** Decisión registrada: ADR-016.

`backend/app/ports/tts.py`, `backend/app/adapters/tts/piper.py`, `POST /voice/speech` y
`GET /voice/speech/{id}` con caché por contenido; en la PWA, `lib/api/speech.ts`,
`features/chat/useSpeech.ts` y los botones «Escuchar», «Más lento», «Detener» con el estado
«Reproduciendo…».

| Verificación | Resultado |
|---|---|
| `uv run pytest` | **177 passed** (156 previos + 21 nuevos) |
| `ruff format --check` / `ruff check` | limpios |
| `npm run typecheck` / `npm run build` | verdes |
| Piper **real** por el adaptador | español 0,276 s, francés 0,280 s; a `speed 0.5` el audio pasa de 84.640 a 139.424 bytes (el doble de duración) |
| Caché | la segunda llamada devuelve los mismos bytes desde el disco |
| Navegador (Chrome headless, conversación francesa) | «Escuchar» → **200 `audio/wav`**, un `<audio>` real de 11,89 s, `playbackRate` 1 y «Reproduciendo…» visible |
| «Detener» | el audio queda pausado y el estado desaparece |
| «Más lento» | `playbackRate` 0,75 **sin** una segunda petición: se reusa el clip |
| Idioma sin voz (conversación inglesa) | «No hay una voz instalada para ese idioma…» y ningún audio nuevo |

**Voces instaladas:** `de_DE-thorsten-high`, `en_US-lessac-high`, `es_MX-claude-high` y
`fr_FR-siwis-medium` (el francés no tiene `high` en el catálogo de Piper). Faltan italiano,
neerlandés y polaco: hay que bajar el `.onnx` a `data/piper-voices`; sin voz, el botón muestra el
error, no falla en silencio.

**L6 — Voces `high` (pedido del humano).** Se instalaron las versiones `high` de alemán, inglés y
español mexicano, y se actualizaron como voces por defecto. Costo medido con el binario real, misma
frase:

| Voz | RTF | Pared | Audio |
|---|---|---|---|
| `de_DE-thorsten-high` | 0,302 | 921 ms | 2,03 s |
| `de_DE-thorsten-medium` | 0,048 | 312 ms | 2,24 s |
| `en_US-lessac-high` | 0,275 | 759 ms | 1,73 s |
| `en_US-lessac-medium` | 0,050 | 292 ms | 1,66 s |
| `es_MX-claude-high` | 0,048 | 442 ms | 2,43 s |
| `es_ES-davefx-medium` | 0,049 | 306 ms | 1,91 s |

Alemán e inglés `high` son ~6× más lentos de inferir (siguen 3× más rápidos que el tiempo real); el
español mexicano `high` pesa lo mismo que un `medium` y por eso casi no cuesta. Los `.onnx` se
verificaron contra el `Content-Length` de Hugging Face antes de conectarlos: el alemán `medium` había
quedado truncado y eso era el «audio en alemán no funciona» de L5.

### Instalación de la voz de salida (una vez por máquina)

`data/` está ignorado por git: el binario y las voces se bajan aparte.

```bash
# 1. Binario (26,5 MB, trae onnxruntime y espeak-ng adentro)
mkdir -p data/piper-bin && curl -L \
  https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_linux_x86_64.tar.gz \
  | tar -xz -C data/piper-bin
# → data/piper-bin/piper/piper

# 2. Voces: el .onnx y el .onnx.json de cada idioma
BASE=https://huggingface.co/rhasspy/piper-voices/resolve/main
mkdir -p data/piper-voices
curl -L -o data/piper-voices/es_ES-davefx-medium.onnx      $BASE/es/es_ES/davefx/medium/es_ES-davefx-medium.onnx
curl -L -o data/piper-voices/es_ES-davefx-medium.onnx.json $BASE/es/es_ES/davefx/medium/es_ES-davefx-medium.onnx.json
curl -L -o data/piper-voices/fr_FR-siwis-medium.onnx       $BASE/fr/fr_FR/siwis/medium/fr_FR-siwis-medium.onnx
curl -L -o data/piper-voices/fr_FR-siwis-medium.onnx.json  $BASE/fr/fr_FR/siwis/medium/fr_FR-siwis-medium.onnx.json
```

Con `PIPER_BIN_PATH=data/piper-bin/piper/piper` (o vacío y `piper` en el PATH) y las voces en
`data/piper-voices`, el botón «Escuchar» funciona. Sin voz para un idioma, el endpoint responde
`voice_not_available` y la UI lo dice.

**L7 — T6: turno de voz completo medido contra la API real.** Backend levantado con la base migrada
y sembrada (`/tmp/f4probe/probe.db`), `PIPER_BIN_PATH` real y el Pi local como tutor. Clip de entrada
generado con **Piper** (voz `fr_FR-siwis-medium`, 3,61 s) y convertido a 16 kHz mono: es voz sintética,
no humana, pero es audio real y del francés correcto.

| Etapa | Medición observada |
|---|---|
| `POST /voice/transcribe` (fr) — primera llamada del proceso | **2,81 s** para 3,61 s de audio (incluye la carga del motor) |
| Transcripción | «Bonjour, je voudrais un café et un croissant, s'il vous plaît.» — exacta, `language_detected: fr`, `duration_ms: 3613` |
| `POST /voice/transcribe` siguiente en el mismo proceso | **0,19 s** |
| `POST /conversations/{id}/messages` | 0,02 s |
| `GET /conversations/{id}/stream` | 11,31 s en total; **primer token a 4,23 s**; eventos `token`, `message_end`, `vocabulary` (sin `correction`: la frase era correcta) |
| Feedback persistido | 8 ítems de vocabulario con `note` y traducción, en el detalle de la conversación |
| `POST /voice/speech` (respuesta del tutor en francés) | **0,32 s**, 154.504 B; repetir la petición: 0,00 s y el mismo `X-Speech-Id` (caché) |
| Turno completo, motor frío | ≈ **14,4 s** (2,81 + 11,31 + 0,32) |
| Turno completo, motor caliente | ≈ **11,8 s** |

El costo del turno lo domina el proveedor del tutor, no la voz: STT caliente y TTS suman 0,5 s.

**Lo que este turno no prueba y queda anotado:** el clip es voz sintética (la calidad con voz humana
sigue sin medirse), y el primer turno de un proceso paga ~2,6 s extra de carga del motor STT — es
exactamente lo que el warm-up al arrancar resolvería, y sigue pendiente en `docs/roadmap.md` junto con
el streaming de voz por frases.
