# Convenciones — Polybot

## 1. Idioma de los artefactos

| Artefacto | Idioma |
|---|---|
| Código, identificadores, nombres de archivos | Inglés |
| Comentarios y docstrings | Inglés |
| Mensajes de error y copy de la interfaz | Español |
| Documentación del repo (`docs/`, `AGENTS.md`) | Español |
| Contenido educativo | Idioma que se estudia |

Excepción: si un término técnico no tiene traducción útil, se deja en inglés.

## 2. Backend (Python / FastAPI)

- Python 3.12+, tipado completo; `mypy` en CI cuando exista CI.
- Formato y lint: `ruff format` + `ruff check`. Sin discusión de estilo en reviews: lo decide la herramienta.
- Async de punta a punta en la capa HTTP. Nada de bloqueos sincrónicos en el event loop (Piper y STT van en hilos o procesos aparte).
- Sin lógica de negocio en routers ni en modelos de base de datos.
- Nombres: `snake_case` para funciones y variables, `PascalCase` para clases, `UPPER_SNAKE` para constantes.
- Excepciones de dominio propias (`ConversationNotFound`, `AudioTooLong`) traducidas a HTTP en `api/`; nunca `raise HTTPException` desde `domain/`.
- Configuración: `pydantic-settings`, sin defaults peligrosos, sin secretos en código.
- Logs estructurados con `request_id`; nunca loguear audio ni el texto completo del usuario por defecto.

## 3. Frontend (TypeScript)

- TypeScript estricto. Tipos del contrato en `src/lib/api/`, escritos a mano contra `docs/api-contract.md` (generarlos desde OpenAPI es una mejora futura).
- Componentes funcionales, sin lógica de negocio: las llamadas a la API viven en `features/*/api` o en hooks.
- Estilos con tokens de `desing.md` §3 (variables CSS). Sin colores hardcodeados fuera de los tokens, y **nunca** copiados de un muestreo del wireframe: los tokens son la fuente, la imagen aporta estructura (ADR-009).
- Nivel de idioma: se muestra como dato de solo lectura. Se edita únicamente en `/languages` con acción explícita (ADR-008).
- Accesibilidad obligatoria: foco visible, etiquetas en íconos, contraste suficiente, transcripción visible como alternativa al audio.
- Estados explícitos para toda vista: vacío, cargando, error, sin permiso.
- Íconos: set lineal coherente (Lucide, según `desing.md`).

## 4. Tests

- Se testea comportamiento observable, no implementación.
- Backend: `unit/` para dominio y casos de uso (sin red ni base), `integration/` para adapters y API.
- Frontend: interacción de componente para flujos críticos; Playwright solo para caminos completos (chat, voz, cambio de idioma).
- Nombres de test en inglés, describiendo la regla: `test_active_language_switch_preserves_previous_history()`.
- Nada de tests que dependan de orden de ejecución, de red real ni de credenciales.
- Comportamiento nuevo: test primero cuando sea ejecutable. Si no lo es, se documenta cómo se verificó.

## 5. Git y revisión

- Ramas: `feat/<tema>`, `fix/<tema>`, `docs/<tema>`.
- Commits convencionales: `feat(chat): stream tutor replies over SSE`.
- Un commit = una unidad revisable de comportamiento, con sus tests y docs.
- PRs de ~400 líneas de cambio como techo cómodo; si es más grande, se parte antes de pedir review.
- El mensaje de commit explica el **por qué**, no repite el diff.

## 6. Documentación

- Cambia el contrato → `docs/api-contract.md` en el mismo commit.
- Cambia una decisión técnica → `docs/decisions.md`.
- Cambia una regla de trabajo para agentes → `AGENTS.md`.
- `desing.md` solo lo cambia el humano, o el agente con pedido explícito.

## 7. Seguridad y privacidad

- Secretos en `.env` (local) o gestor de secretos; jamás en el repo ni en logs.
- Audio del usuario: no se persiste sin consentimiento explícito; si se persiste, el usuario puede borrarlo.
- Validar todo input en el borde: tamaño, tipo MIME real, duración, idioma.
- CORS restringido al origen de la PWA.
- Dependencias: ninguna nueva sin justificación escrita en el PR.

## 8. Errores para humanos

- Mensaje claro, en español, sin códigos crudos ni trazas.
- Siempre una acción de recuperación: «Reintentar», «Volver a escribir», «Revisar permisos».
- Distinguir fallo de red, fallo del modelo y límite alcanzado: son problemas distintos para el usuario.
