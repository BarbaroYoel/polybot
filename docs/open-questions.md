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

**Estado: RESUELTA → ADR-010.** React 18 + Vite + TypeScript, CSS propio sobre los tokens de `desing.md` §3 y
`react-router-dom`. Sin librería de UI ni framework de CSS.

## Q4 — Motor STT: confirmar "Cactus Whistle"

**Estado: RESUELTA → ADR-015.** Es **Whistle** de Cactus Compute (`huggingface.co/Cactus-Compute/whistle`):
corre local por CPU, soporta streaming nativo y cubre inglés, alemán, francés, español, italiano, neerlandés y
polaco. El vehículo es el paquete `cactus-needle`. F4 puede empezar; su primera tarea es verificarlo en esta
máquina con un clip real.

## Q5 — ¿La PWA necesita autenticación en v0?

**Estado: RESUELTA → ADR-012.** Sin auth en v0: la API queda abierta en local y la decisión se retoma antes de
exponerla. No hay entidad `user` en el modelo; el «perfil de usuario» del wireframe sigue decorativo.
