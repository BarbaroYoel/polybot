# Roadmap — Polybot

Cada fase termina con algo verificable por un humano. Estado actual: **F0**.

## F0 — Base documental

- [x] `desing.md` con producto, pantallas, estados y criterios de aceptación.
- [x] Contrato de trabajo para agentes (`AGENTS.md`).
- [x] Arquitectura, stack, contrato de API, convenciones y decisiones.
- [x] Repositorio Git inicializado y primer commit (`4c27b58`).
- [ ] Repositorio remoto y política de ramas.

**Salida:** cualquier agente puede leer el repo y saber qué construir sin inventar decisiones.

## F1 — Carcasa de la PWA con datos de ejemplo — **completada** (rama `feat/f1-pwa-shell`)

Alcance: `desing.md` §13, puntos 1–5. Detalle y evidencia: `odd/tasks/f1-pwa-shell.md`.

- [x] Shell con sidebar, cabecera y navegación (todas las secciones).
- [x] Inicio con las tarjetas de resumen y el historial del idioma activo, separado de la conversación (`/` y `/chat/:conversationId`, ADR-011).
- [x] Pantalla de conversación completa: mensajes, sugerencias rápidas, compositor.
- [x] Selector de idioma con contexto persistente entre recargas.
- [x] Vistas base de Lecciones, Planes, Traducción y Progreso con datos de ejemplo identificados.
- [x] Estados vacíos, de carga, de error y de permiso; banner sin conexión.
- [x] Responsive escritorio / tablet / móvil.
- [x] Build y typecheck verdes; verificación de checklist §14 registrada en el documento de la feature.

**Verificación:** checklist de `desing.md` §14 completa (tabla en `odd/tasks/f1-pwa-shell.md` §Verificación).
La separación inicio / conversación se verificó con una sonda de geometría en Chrome headless sobre ocho viewports
(`odd/tasks/chat-home-split.md`).
El permiso de micrófono queda explícitamente para F4, cuando exista el micrófono.

## F2 — Esqueleto del backend y contrato real

- FastAPI con `/health`, configuración tipada, sobre de error uniforme.
- Implementación de `/languages` y `/conversations` con persistencia.
- Iteración del contrato contra la UI, sin romper `docs/api-contract.md`.

**Verificación:** la PWA de F1 consume datos reales en esas dos secciones.

## F3 — Chat de texto real

- Puerto `LLM` + primer adaptador; prompt del tutor versionado.
- Streaming SSE del turno, con cancelación.
- Correcciones y vocabulario sugerido al cerrar el turno.

**Verificación:** conversación real por texto, con historial y cambio de idioma sin mezclar datos.

## F4 — Voz

- STT (decidir el modelo: ver `docs/stack.md`).
- TTS con Piper, streaming por frases y caché.
- Estados visibles: escuchando, transcribiendo, pensando, reproduciendo. Edición del texto transcripto antes de enviar.

**Verificación:** turno de voz completo con latencia medida y aceptable; texto siempre visible como alternativa.

## F5 — Lecciones y planes de estudio

- Catálogo, lección con ejercicios, feedback y cierre.
- Creación de plan a partir de un objetivo; sesiones con estado.

**Verificación:** completar una lección y ver el progreso reflejado.

## F6 — Progreso

- Resumen, evolución por destreza, errores frecuentes, historial.
- Nivel como dato trazable, no como medición infalible.

**Verificación:** el progreso refleja las sesiones reales de F3–F5.

## F7 — Intérprete en tiempo real

- WebSocket, segmentos continuos, transcripción + traducción por turno.
- Aviso visible de latencia y precisión variables.

**Verificación:** conversación de prueba con dos idiomas y fragmentos ordenados temporalmente.

## Fuera de alcance

Pagos, gamificación extensa, redes sociales, marketplace, personajes 3D, analíticas complejas, identidad de marca definitiva
(`desing.md` §13).
