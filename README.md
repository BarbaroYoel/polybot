# Polybot

PWA de tutor de idiomas guiada por IA, centrada en el chat, con voz como capacidad de primera clase.

**Estado:** F1 — carcasa de la PWA con datos de ejemplo. Sin backend todavía.

## Cómo correrlo

```bash
cd frontend
npm install
npm run dev      # http://localhost:5173
```

```bash
npm run typecheck   # TypeScript estricto
npm run build       # typecheck + bundle de producción
```

Los datos que se ven son de ejemplo y la interfaz lo dice: no hay API conectada.
Los controles sin función están deshabilitados con un `title` que explica en qué fase llegan.

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

Frontend **React 18 + Vite + TypeScript** (ADR-010) · backend **FastAPI** · TTS **Piper** · PWA independiente del harness · UI en español, estética monocromática.
Pendiente: motor STT, base de datos, motor del tutor. Ver `docs/stack.md`.

## Cómo arrancar

El frontend de F1 ya corre (ver arriba). Lo siguiente está en `docs/roadmap.md` (F2: esqueleto del backend).

## Skills del proyecto

`.agents/skills` incluye `frontend-design`, `ui-ux-pro-max` y `web-design-guidelines`.
El índice generado está en `.atl/skill-registry.md`.

## Licencia

Sin definir.
