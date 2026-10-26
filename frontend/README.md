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

La API vive en `http://localhost:8000/api/v1`. `VITE_API_BASE_URL` (en `frontend/.env`) cambia ese
destino. Para ver datos, el backend necesita la base migrada y sembrada (ver [`README.md`](../README.md)
raíz).

## Rutas

| Ruta | Vista |
|---|---|
| `/` | Inicio: tarjetas del idioma activo e historial de conversaciones |
| `/chat/:conversationId` | Conversación: hilo y compositor |
| `/lessons` | Catálogo de lecciones del idioma activo |
| `/lessons/:lessonId` | Práctica, corrección y resultado de una lección |
| `/plans` | Plan de estudio, cronograma por semanas y ajuste explícito |
| `/languages` | Idiomas: activar, agregar, cambiar nivel, archivar |
| `/translate`, `/progress`, `/settings` | Vistas base de F1, todavía sin función completa |

## Contexto por idioma

- El idioma activo sale de `GET /languages` (`is_active`); el cliente no lo adivina ni lo guarda
  como fuente de verdad.
- Lecciones, planes y conversaciones se consultan con `language_id`. Un recurso de otro idioma es
  un 404 con recuperación, no una lista vacía.
- El estado de cada lección y de cada sesión, la próxima lección/sesión y el cronograma vienen del
  backend; la UI no inventa progreso ni fechas de calendario.

## Verificación

No hay suite de tests de frontend decidida ([`docs/stack.md`](../docs/stack.md)). Los checks
actuales son `npm run typecheck` y `npm run build`; la verificación funcional se hace contra una API
aislada y se registra en [`docs/roadmap.md`](../docs/roadmap.md) (F5).
