# Polybot

PWA de tutor de idiomas guiada por IA, centrada en el chat, con voz como capacidad de primera clase.

**Estado:** F0 — diseño y documentación. Todavía no hay código.

## Qué hay en este repositorio

| Archivo | Para qué |
|---|---|
| [`desing.md`](./desing.md) | Fuente de verdad de producto y UI: pantallas, estados, tokens, criterios de aceptación. |
| [`AGENTS.md`](./AGENTS.md) | Contrato de trabajo para agentes (Pi, OpenCode, Codex, Cursor…). Empezá por acá si sos un agente. |
| [`docs/architecture.md`](./docs/architecture.md) | Capas, límites, mapa de carpetas y flujos. |
| [`docs/stack.md`](./docs/stack.md) | Qué está decidido y qué falta decidir. |
| [`docs/api-contract.md`](./docs/api-contract.md) | Contrato v0 entre frontend y backend. |
| [`docs/conventions.md`](./docs/conventions.md) | Código, tests, commits, idioma de artefactos. |
| [`docs/decisions.md`](./docs/decisions.md) | ADRs aceptadas. |
| [`docs/open-questions.md`](./docs/open-questions.md) | Decisiones de producto/UI todavía abiertas. |
| [`grayscale_language_tutor_chat_ui.png`](./grayscale_language_tutor_chat_ui.png) | Wireframe de referencia (1448×1086). |
| [`docs/roadmap.md`](./docs/roadmap.md) | Fases F0–F7 y criterios de verificación. |

## Stack definido

Backend **FastAPI** · TTS **Piper** · frontend PWA independiente del harness · UI en español, estética monocromática.
Pendiente: framework del frontend, motor STT, base de datos. Ver `docs/stack.md`.

## Cómo arrancar

No hay build todavía. El siguiente paso está en `docs/roadmap.md` (F0 → F1).

## Skills del proyecto

`.agents/skills` incluye `frontend-design`, `ui-ux-pro-max` y `web-design-guidelines`.
El índice generado está en `.atl/skill-registry.md`.

## Licencia

Sin definir.
