# Preguntas abiertas — Polybot

Decisiones de producto u UI que **no** están resueltas. Un agente no las resuelve por su cuenta:
si su tarea las toca, pregunta antes de implementar.

Regla de precedencia: si el wireframe y el texto de `desing.md` difieren, manda el texto (ADR-009).

## Q1 — ¿Los niveles A1/B1/B2 del sidebar son un control o un dato?

**Estado: RESUELTA → ADR-008.** Manda el texto de `desing.md`: el sidebar muestra **un solo badge** con el nivel actual, no interactivo. El nivel se cambia solo en `/languages`, con acción explícita.

## Q2 — Los tokens de burbujas no coinciden con el wireframe

**Estado: RESUELTA → ADR-009.** La tabla de `desing.md` §3 es la fuente de los colores; el wireframe aporta estructura y jerarquía, no valores. Ningún componente hardcodea un color medido de la imagen. Los valores medidos quedan como referencia de diagnóstico:

| Elemento | Wireframe | Token en `desing.md` §3 |
|---|---|---|
| Burbuja del tutor | `#EFEFEF` | `--bg-surface` `#FAFAFA` («blanco o gris muy tenue») |
| Burbuja del usuario | `#DCDBDB` | `--bg-user-message` `#EDEDED` |
| Fondo del área de chat | `#FEFEFE` | `--bg-app` `#FFFFFF` |
| Ítem activo del sidebar | `#CCCCCC` | `--bg-hover` `#ECECEC` |

El orden relativo se mantiene (usuario más oscuro que tutor), pero los valores difieren y el ítem activo es bastante más oscuro.

**Necesita:** nada. Resuelta en ADR-009.

## Q3 — Framework del frontend

Ver `docs/stack.md` §Pendiente. Bloquea el esqueleto de `frontend/` (F1).

## Q4 — Motor STT: confirmar "Cactus Whistle"

El usuario lo mencionó como modelo de audio a texto. Falta el nombre exacto, si corre local o en servidor,
si soporta streaming y qué idiomas cubre. Bloquea F4, no F1.

## Q5 — ¿La PWA necesita autenticación en v0?

Sin auth la API queda abierta en local. Define si el «perfil de usuario» del wireframe existe como entidad o es decorativo.
Bloquea F2 en adelante.
