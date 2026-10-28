# Estabilización para uso privado — 2026-10-28

## Pedido y alcance

Dejar la aplicación F1–F7 utilizable, conservar los datos e integrar lo verificado en `main`.
El usuario autorizó subagentes con `opencode-go/deepseek-v4.1-flash#max`, instalar Piper y cuatro
voces, y actualizar versiones mayores de Vite y React Router para corregir vulnerabilidades.
Sin despliegue público, autenticación nueva ni cambio de framework de testing.

## Arranque y privacidad

- `scripts/start-local.sh` inicia los dos servidores en loopback, usa el proxy `/api/v1` y los
  detiene al terminar. No instala, migra, siembra ni elimina datos.
- Rechaza puertos ocupados en vez de cambiar de puerto o terminar procesos ajenos.
- README documenta preparación, arranque, voces y acceso privado por Codespaces.
- Los respaldos `*.db.bak-*` quedan ignorados para evitar subir datos de usuario accidentalmente.
- La configuración local conserva el proveedor OpenCode existente; Piper usa una ruta absoluta
  en `.env`, ignorado por Git. Los modelos y el binario viven en `data/`, también ignorado.
- Solo el puerto 5173 está reenviado en Codespaces, con visibilidad **privada**; el backend no se
  publica. Esto no añade autenticación a la API: no debe exponerse públicamente.

## Verificación real ejecutada

### Checks de cierre

- `uv run --frozen --offline pytest -q`: **296 passed in 51.27s**.
- `uv run --frozen --offline ruff check .`: limpio.
- `uv run --frozen --offline ruff format --check .`: 116 archivos formateados.
- `npm run typecheck`: exit 0.
- `npm run build`: Vite 7.3.7, 97 módulos, build correcto en 3,10 s.
- `npm audit`: **cero vulnerabilidades**.
- `git diff --check`: limpio antes de integrar.
- Integración por fast-forward en `main`, sin push. Arranque y sonda de permisos, reproducción y
  WebSocket repetidos desde `main`; sin excepciones en el log del backend y sin cambios en los
  conteos de la base original.

### Dependencias

Actualización autorizada: Vite 7.3.7, esbuild 0.28.2 y React Router 7.18.5, manteniendo React 18 y
`@vitejs/plugin-react` 4.7.0. `npm install`, `npm audit` y `npm audit --omit=dev` terminan con **cero
vulnerabilidades**; typecheck y build de Vite 7 pasan. Requisitos y decisión: ADR-023.

Las operaciones que persisten conversaciones, intentos o planes se ejecutaron contra
`127.0.0.1:8010`, con una copia SQLite en `/tmp/opencode/polybot-verification/polybot.db`.
La base original conserva sus dos conversaciones, siete mensajes y cero intentos de lección.

| Flujo | Evidencia |
|---|---|
| Salud y proxy | `/api/v1/health` devuelve 200 directamente y por 5173. |
| Chat con proveedor real | Dos turnos SSE, primer texto a 3,3 s; cierre completo a 11–12 s. |
| Cierre educativo | `message_end → blocks → correction → vocabulary`; error `à le café → au café`, feedback y bloques persistidos. |
| Idempotencia | Repetir el envío con la misma clave devuelve el mismo mensaje, sin duplicar el turno. |
| Traducción | Mensaje persistido, caché idempotente y fragmento sin estado; 1,7–4,7 s. |
| Lecciones | Lección francesa de cuatro ejercicios (tres escritos y uno de elección): 4/4, resultado persistido y catálogo avanzado. |
| Plan | Creación, ajuste de frecuencia/minutos y sesión completada derivada del intento. |
| Progreso | Francés avanza; inglés y alemán no cambian. |
| STT | Clip humano de 11 s, WAV 16 kHz mono 16 bits: transcripción exacta en unos 5 s. |
| Intérprete real | 16 parciales, tres segmentos y tres traducciones; sin errores, cierre 1000, 9,1 s en total. |
| TTS real | Español, inglés, francés y alemán: WAV válido y recuperación del mismo clip cacheado. |
| Navegador tras actualizar dependencias | 60 combinaciones de rutas y anchos (320, 360, 375, 390, 768 y 1280 px), seis navegaciones por Link y recarga: sin overflow ni errores de consola; 196 peticiones API por el proxy del mismo origen. |
| Micrófono de chat | Escuchando y Transcribiendo visibles; transcripción editable, sin envío automático ni mensajes nuevos. |
| Permisos tras actualizar dependencias | Chat e intérprete: cero llamadas al micrófono al cargar, denegación simulada y reintento tras conceder; sin envío automático. |
| Proxy WS tras actualizar dependencias | Audio real desde la UI por 5173: 45 frames PCM, cinco segmentos y traducción final recibida; cancelación visible. |
| Reproducción | Escuchar, Detener y Más lento verificados en navegador. |
| Launcher | Sintaxis Bash válida; inicio desde fuera del repo y proxy listos; puerto ocupado rechazado con exit 1; SIGINT y SIGTERM cierran ambos servidores sin procesos huérfanos. Reinicio inmediato comprobado. |

La sonda de navegador usa Playwright y Chrome headless ya presentes en la caché de la máquina,
sin introducir un framework nuevo en el repositorio. El permiso denegado se simula con
`NotAllowedError`: no equivale a comprobar el diálogo real del navegador del usuario.

Los artefactos de verificación quedan fuera del repo, en `/tmp/opencode/polybot-real-verify/`
y `/tmp/opencode/f7-t6/`; no contienen credenciales y no son requisitos para arrancar la app.

## Correcciones de comportamiento

- La cabecera móvil usa dos filas y mantiene el saludo legible sin desbordar.
- Chat e intérprete muestran instrucciones y «Reintentar micrófono» tras denegar el permiso.
  El usuario debe habilitarlo en su navegador; no se promete abrir ajustes desde la app. La
  denegación se identifica por el tipo de error, no buscando palabras en su texto.
- Dos creaciones de plan concurrentes ya no filtran un `IntegrityError` como 500: el adaptador
  traduce exclusivamente la restricción única `study_plans.language_id` a `PlanAlreadyExists` (409).
  Otra violación de integridad sigue propagando. Ambas reglas tienen regresión automatizada;
  cinco pruebas concurrentes reales devolvieron 201 + 409.
- El cierre del intérprete tolera la desconexión esperada del cliente, incluida la cancelación
  tras denegar permisos. No se ocultan otros errores inesperados de cierre; ambos comportamientos
  tienen regresión automatizada.

## Límites que no bloquean el uso privado

- El CLI puede emitir toda la respuesta como un único delta; el cierre educativo tarda más que el
  primer texto. La latencia depende del proveedor, no se promete conversación instantánea.
- El intérprete sigue segmentando cada 4,5 s con solape; puede partir frases y no reproduce su
  traducción por voz (ADR-022).
- La calidad del proveedor no es determinista: en la última sonda un segmento en inglés volvió
  sin traducir pese al destino español. Repetir ese mismo texto por `/translate` sí produjo
  español, al igual que otras dos frases de control. Es un límite observado del modelo, no una
  garantía de traducción perfecta; la captura por ventanas también puede degradar la transcripción.
- Se instalaron las cuatro voces autorizadas. Italiano, neerlandés y polaco requieren sus modelos
  adicionales; sin ellos el error es `voice_not_available`.
- No se decidió una suite de tests de frontend; las sondas de navegador no sustituyen esa decisión.
- Streaming de voz por frases y precarga de STT siguen como mejoras de F4, no como funciones nuevas
  prometidas por esta estabilización.
- Sin auth ni servicio de producción: conservar el acceso privado. El Codespace debe permanecer
  encendido y el proveedor de IA sigue requiriendo conexión.
