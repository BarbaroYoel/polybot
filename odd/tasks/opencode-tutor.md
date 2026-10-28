# Tutor sobre OpenCode — adaptador alternativo del puerto `LLM`

Cambio pedido por el humano: el proyecto se conectaba a Pi, que no está instalado en este Codespace,
y el chat/traducción fallaban con `llm_unavailable`. Decisión registrada: ADR-019.

## Specs

**S1 — El puerto no cambia.** Dominio, casos de uso, endpoints, contrato y PWA siguen iguales: el
harness es un detalle de `adapters/llm` (ADR-004). El adaptador nuevo implementa `LlmPort` completo:
streaming del turno, cierre con correcciones/vocabulario, traducción y comentario de lección.

**S2 — Selección por configuración.** `LLM_PROVIDER=pi|opencode`. `pi` sigue siendo el default para
no romper instalaciones existentes; este entorno usa `opencode` en su `.env` local. `OPENCODE_MODEL`,
`OPENCODE_AGENT` y `OPENCODE_TIMEOUT_SECONDS` se configuran por entorno.

**S3 — Aislamiento.** Cada invocación corre en un directorio temporal, con el agente de solo lectura
`plan`, sin sesión persistente y con timeout. El prompt completo viaja como mensaje porque el CLI de
OpenCode no acepta `--system-prompt`.

**S4 — Respuestas validadas igual que con Pi.** El cierre del turno, la traducción y el comentario de
lección usan `adapters/llm/parsing.py`, compartido por ambos adaptadores: un cambio de proveedor no
puede cambiar qué se considera una respuesta usable.

**S5 — Nada de SDK nuevo.** Se ejecuta el CLI `opencode` ya instalado y autenticado. No se agrega una
dependencia Python ni una clave al repositorio.

**S6 — Fallos degradados.** Un binario ausente, un error del proveedor, una respuesta vacía o
ilegible y un timeout se traducen a `LlmUnavailable`/`LlmTimeout`; el chat conserva el mensaje del
usuario y la lección se corrige igual sin comentario.

## Tasks

| ID | Specs | Alcance | Estado |
|---|---|---|---|
| T1 | S1–S6 | `OpenCodeCliAdapter`, config, composición en `main.py`, parsing compartido y tests con fixture JSONL | completada; 240 tests verdes |
| T2 | S3–S6 | Verificación real contra OpenCode, UI y documentación (ADR-019, stack, README, env.example) | completada |

## Log

**L1 — pedido y diagnóstico.** El humano preguntó a qué se conectaba el proyecto y pidió que use
OpenCode. Se confirmó que el adaptador era `PiCliAdapter`, que `pi` no está en el `PATH` y que
`POST /translate` devolvía 502 `llm_unavailable`. OpenCode v2.1.4 está instalado y su servicio en
segundo plano responde en `http://127.0.0.1:49374`.

**L2 — implementación.** Se agregó `backend/app/adapters/llm/opencode.py`:

- `opencode run --format json --agent plan [--model <modelo>] -- <prompt>`;
- lectura de eventos `text` por JSONL, con manejo de partes que se reenvían crecidas;
- `error` del proveedor, salida distinta de cero, respuesta vacía o desmesurada → `LlmUnavailable`;
- timeout propio, directorio temporal y `start_new_session` para cancelar el grupo de procesos;
- cierre, traducción y comentario reutilizan `parsing.py` (movido desde `pi.py`).

Config: `LLM_PROVIDER`, `OPENCODE_BIN_PATH`, `OPENCODE_MODEL`, `OPENCODE_AGENT`,
`OPENCODE_TIMEOUT_SECONDS`. `main.py` elige el adaptador. `docs/env.example` documenta las variables.

**L3 — verificación.** `uv run pytest` → **240 passed**; `ruff format --check` y `ruff check`
limpios. Tests nuevos: 20 escenarios del adaptador con `tests/fixtures/fake_opencode.py` (streaming
por partes, parte acumulativa, prompts, argv, cwd fuera del repo, error, exit code, JSON roto, vacío,
respuesta desmesurada, timeout, cancelación, feedback, traducción, lección y binario ausente).

**L4 — llamada real, con `LLM_PROVIDER=opencode`.** Configuración local (`.env`, ignorado):
`OPENCODE_MODEL=opencode-go/deepseek-v4.1-flash`, `OPENCODE_AGENT=plan`,
`OPENCODE_TIMEOUT_SECONDS=120`. Observado contra la API real:

- `POST /api/v1/translate` → **200 en 3 s**: `{"translation": "¿Cómo estás?", "detected_source": "en"}`.
- Turno de chat completo en **10 s** por SSE: un evento `token` con la respuesta del tutor
  («Bonjour ! Bien sûr, un café…»), `message_end`, `correction` («s il vous plaît» → «s'il vous
  plaît») y `vocabulary` (seis términos). El cierre quedó persistido y sobrevive a la recarga.
- PWA con Chromium headless sobre `/chat/{id}`: la respuesta, la tarjeta de corrección y la de
  vocabulario se ven; cero errores de consola; las llamadas salen por `.../api/v1` a través del proxy
  de Vite. Captura en `/tmp/f6-chat-opencode.png`.

Antes del cambio, el mismo entorno devolvía `llm_unavailable` porque `pi` no estaba instalado
(`pi could not start: FileNotFoundError`), confirmado con `POST /translate` → 502.

**Límites conocidos:**

1. El streaming depende de las partes de texto que emite OpenCode: el primer `token` puede traer la
   respuesta completa, como en la prueba (un solo delta), en vez de token por token.
2. `plan` es de solo lectura, pero no es un sandbox: OpenCode conserva herramientas de lectura. Se
   acota con el directorio temporal y el agente; un agente sin herramientas queda como mejora.
3. La calidad, latencia y costo dependen del modelo configurado. El modelo por defecto de esta
   instalación no estaba habilitado por privacidad; por eso el `OPENCODE_MODEL` local es explícito.
4. Pi sigue siendo el default del código; OpenCode se activa por entorno. La suite corre con dobles y
   no invoca ninguno de los dos CLIs.
