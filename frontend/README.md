# Polybot — frontend

PWA de Polybot: React 18 + Vite + TypeScript, CSS propio sobre los tokens de
[`desing.md`](../desing.md) §3. Solo habla HTTP con la API
([`docs/api-contract.md`](../docs/api-contract.md)); no conoce el harness del tutor.

## Comandos

| Qué | Comando |
|---|---|
| Instalar dependencias | `npm install` |
| Servidor de desarrollo | `npm run dev` → http://localhost:5173 |
| Typecheck | `npm run typecheck` |
| Build de producción | `npm run build` |

La API vive en `http://localhost:8000/api/v1`. `VITE_API_BASE_URL` (en `frontend/.env` o
`.env.local`) cambia ese destino. Para ver datos, el backend necesita la base migrada y sembrada (ver
[`README.md`](../README.md) raíz).

## Codespaces

Para abrir la PWA por la URL reenviada (`https://<codespace>-5173.app.github.dev`) hacen falta dos
cosas:

- `server.allowedHosts: [".app.github.dev"]` (y lo mismo en `preview`) en `vite.config.ts`; sin eso
  Vite 5 responde 403 a ese host.
- `VITE_API_BASE_URL=/api/v1` en `frontend/.env.local` (ignorado por git). El cliente pide la API al
  mismo origen y Vite la proxya a `localhost:8000`, así no hay CORS ni un segundo puerto expuesto.

El puerto 5173 se abre desde **Ports**. Si se usa SSH o GitHub CLI, `gh codespace ports forward
5173:15173 -c <codespace>` mantiene el reenvío. Dejar la visibilidad en **private**: la API no tiene
autenticación todavía.

## Rutas

| Ruta | Vista |
|---|---|
| `/` | Inicio: tarjetas del idioma activo e historial de conversaciones |
| `/chat/:conversationId` | Conversación: hilo y compositor |
| `/lessons` | Catálogo de lecciones del idioma activo |
| `/lessons/:lessonId` | Práctica, corrección y resultado de una lección |
| `/plans` | Plan de estudio, cronograma por semanas y ajuste explícito |
| `/progress` | Progreso del idioma activo: resumen, destrezas, errores e historial |
| `/languages` | Idiomas: activar, agregar, cambiar nivel, archivar |
| `/translate`, `/settings` | Vistas base de F1, todavía sin función completa |

## Contexto por idioma

- El idioma activo sale de `GET /languages` (`is_active`); el cliente no lo adivina ni lo guarda
  como fuente de verdad.
- Lecciones, planes, conversaciones y progreso se consultan con `language_id`. Un recurso de otro
  idioma es un 404 con recuperación, no una lista vacía.
- El estado de cada lección y de cada sesión, la próxima lección/sesión, el cronograma y todo el
  progreso vienen del backend; la UI no inventa actividad, duración ni fechas de calendario. El
  nivel se muestra como dato y se edita solo en `/languages`.

## Verificación

No hay suite de tests de frontend decidida ([`docs/stack.md`](../docs/stack.md)). Los checks
actuales son `npm run typecheck` y `npm run build`; la verificación funcional se hace contra una API
aislada y se registra en [`docs/roadmap.md`](../docs/roadmap.md). En F6, typecheck y build quedaron
verdes, la API se probó por HTTP y la pantalla se verificó con Chromium headless en escritorio y
móvil: sin errores de consola y sin desborde horizontal.
