# AGENTS.md — Polybot

Contrato de trabajo para cualquier agente (Pi, OpenCode, Codex, Cursor, Claude Code) que toque este repositorio.
Léelo completo antes de escribir una sola línea.

**Regla madre:** si una decisión no está acá, en `desing.md` ni en `docs/decisions.md`, no la inventes.
Propónla, regístrala como pendiente y pregunta.

**Precedencia:** si el wireframe y el texto de `desing.md` difieren, manda el texto (ver ADR-009).

## 1. Qué es Polybot

PWA de tutor de idiomas guiada por IA, centrada en el chat, con la voz como capacidad de primera clase.
Un solo idioma activo a la vez; conversaciones, lecciones, planes y progreso aislados por idioma.

Fuente de verdad del producto y de la interfaz: **`desing.md`** (wireframe incluido). No lo reinterpretes.

## 2. Orden de lectura obligatorio

1. `desing.md` — producto, pantallas, estados, criterios de aceptación.
2. `docs/architecture.md` — capas, límites y flujos.
3. `docs/stack.md` — qué está decidido y qué no.
4. `docs/api-contract.md` — contrato frontend ↔ backend.
5. `docs/conventions.md` — código, tests, commits.
6. `docs/roadmap.md` — en qué fase estamos.
7. `docs/decisions.md` — decisiones registradas.
8. `docs/open-questions.md` — preguntas abiertas: no las resuelvas solo, preguntá.

## 3. Reglas no negociables

- **El chat es el centro.** Todo lo demás complementa la conversación; nada de dashboards recargados.
- **La UI habla español.** El código, identificadores y comentarios van en inglés. El contenido educativo puede estar en cualquier idioma.
- **Un idioma activo a la vez.** Cambiar de idioma cambia el contexto; nunca mezcla ni borra historiales.
- **Datos por idioma.** Toda consulta de conversaciones, lecciones, planes y progreso se filtra por `language_id`.
- **Nada de acoplar el frontend a un harness.** La UI no conoce Pi, OpenCode ni ningún orquestador; solo habla con la API.
- **Ningún botón decorativo.** Si un control no tiene función, no se muestra o se marca explícitamente como prototipo.
- **Audio con permiso y estado visible.** Escuchando / Transcribiendo / Pensando / Reproduciendo siempre visibles.
- **No prometer offline** de conversación ni traducción sin modelos locales. La carcasa de la PWA sí puede funcionar offline.
- **No agregar funciones, dependencias ni integraciones** fuera de `desing.md` y `docs/roadmap.md`.
- **No persistir audio** sin consentimiento explícito y control visible del usuario.

## 4. Arquitectura en 30 segundos

Monolito modular: **API FastAPI** con capas `domain → application → adapters`, un **frontend PWA** independiente
y proveedores externos (LLM, STT, TTS) detrás de *puertos* reemplazables.

```
api/  →  application/  →  domain/          (dependencias hacia adentro)
adapters/  implementan  ports/             (piper, stt, llm, db)
```

`domain/` no importa FastAPI, base de datos ni SDKs de proveedores. Si necesitás eso, estás en la capa equivocada.
Detalle completo en `docs/architecture.md`.

## 5. Comandos

Hoy **no existe código**: este repositorio solo contiene diseño y documentación.
No inventes comandos de build, test ni migración, y no ejecutes instaladores por iniciativa propia.

Cuando exista el esqueleto, esta sección es la única fuente de comandos del proyecto y se actualiza en el mismo
commit que los agrega.

## 6. Cómo trabajar

1. Leé los documentos del punto 2 antes de escribir. Si el pedido contradice `desing.md`, preguntá; no resuelvas el conflicto por tu cuenta.
2. Trabajá en cambios chicos y revisables: una unidad de comportamiento por vez.
3. Comportamiento nuevo o cambiado: test primero cuando haya forma de ejecutarlo; si no, explicá cómo verificaste.
4. Todo cambio de contrato (endpoint, campo, error) actualiza `docs/api-contract.md` en el mismo commit.
5. Toda decisión técnica con consecuencias actualiza `docs/decisions.md`.
6. Citá evidencia con `ruta:línea`. Si no verificaste algo, decí que no lo verificaste.
7. No commitees, no hagas push y no abras PRs salvo pedido explícito.

## 7. Límites

- No modifiques `desing.md` sin pedido explícito del humano: es la referencia visual aprobada.
- No toques `.agents/`, `.atl/` ni `skills-lock.json`: los gestiona el tooling de skills.
- No agregues archivos de configuración de un framework que todavía no se decidió (ver `docs/stack.md`).
- No reestructures carpetas acordadas en `docs/architecture.md` sin registrar la decisión.
- No resuelvas una pregunta de `docs/open-questions.md` por tu cuenta: preguntá antes de implementar.

## 8. Definición de terminado

- El comportamiento pedido funciona y se verificó de la forma que el pedido indica.
- Tests o verificación proporcional, ejecutados, con su salida real.
- Documentación afectada actualizada (`api-contract`, `conventions`, `decisions`, `roadmap`).
- Nada de TODOs silenciosos: lo pendiente se registra o se dice explícitamente.
- Riesgo declarado: qué se tocó y qué podría romperse.
