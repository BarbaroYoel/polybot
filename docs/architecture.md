# Arquitectura — Polybot

Estado: propuesta inicial. Lo decidido está en `docs/decisions.md`; lo no decidido, en `docs/stack.md`.

## 1. Principios

1. **Monolito modular antes que microservicios.** "Escalable" significa límites claros y procesos sin estado, no diez servicios desde el día uno.
2. **El dominio no conoce infraestructura.** Reglas de negocio puras, testeables sin base de datos, sin red y sin FastAPI.
3. **Proveedores detrás de puertos.** LLM, STT y TTS son reemplazables: el resto del sistema no sabe cuál se usa.
4. **Frontend desacoplado.** La PWA consume HTTP/SSE y no conoce el harness que ejecuta al tutor.
5. **Streaming donde el usuario lo percibe.** Texto del tutor y audio se transmiten por partes; nada de esperar la respuesta completa.
6. **Stateless en la API.** El estado vive en la base; los procesos se pueden replicar sin sticky sessions (salvo el canal de voz en vivo).

## 2. Mapa de carpetas

```text
polybot/
├── AGENTS.md                 # contrato para agentes
├── desing.md                 # fuente de verdad de producto y UI
├── docs/                     # arquitectura, stack, contrato, convenciones, decisiones, roadmap
├── backend/
│   ├── app/
│   │   ├── main.py           # creación de la app, routers, middleware
│   │   ├── api/v1/           # routers HTTP finos: validan y delegan
│   │   ├── core/             # config, logging, errores, dependencias
│   │   ├── domain/           # entidades y reglas puras
│   │   ├── application/      # casos de uso y orquestación
│   │   ├── ports/            # interfaces: LLM, STT, TTS, repositorios
│   │   └── adapters/         # piper, stt, llm, db, storage
│   ├── migrations/
│   └── tests/
│       ├── unit/             # dominio y casos de uso
│       └── integration/      # adapters y API
└── frontend/
    ├── src/
    │   ├── app/              # rutas / entrada
    │   ├── components/       # UI reutilizable (ver desing.md §10)
    │   ├── features/         # home, chat, lessons, plans, translate, progress, languages, settings
    │   ├── lib/api/          # cliente HTTP y tipos del contrato
    │   └── styles/           # tokens y estilos base
    └── public/               # manifest, íconos, assets
```

La estructura de `frontend/` es de SPA (React + Vite, ADR-010): `src/app/` contiene rutas y entrada.

## 3. Regla de dependencias

```text
api/v1  ──▶  application  ──▶  domain
                │
                ▼
             ports/  ◀── adapters/ (piper, stt, llm, db)
```

- `domain/` no importa FastAPI, SQLAlchemy ni SDKs de proveedores.
- `application/` depende de `ports/`, nunca de `adapters/` concretos.
- `adapters/` implementan `ports/` y son los únicos que hablan HTTP hacia afuera o SQL hacia adentro.
- `api/v1/` no contiene reglas de negocio: valida, llama a un caso de uso y serializa.

Un import que cruce estas flechas al revés es un defecto de arquitectura, no un atajo.

## 4. Flujos principales

### 4.1 Chat de texto

1. `POST /api/v1/conversations/{id}/messages` con el texto del usuario (idempotente por `Idempotency-Key`).
2. `application` persiste el mensaje y, al abrir el turno, un mensaje del tutor en `streaming`.
3. Se llama al puerto `LLM` con el prompt del tutor y se transmite la respuesta por `GET .../stream` (SSE).
4. Al terminar se guarda el mensaje del tutor como `sent` y se emite `message_end`.
5. Al cerrar el turno, una segunda invocación del puerto `LLM` produce correcciones y vocabulario; se persisten y se
   emiten como `correction` y `vocabulary`. Un fallo de ese cierre no rompe la conversación: el texto ya está guardado.

El adaptador del tutor es una instancia de Pi por invocación, aislada de herramientas y del repositorio (ADR-013).
La base es la única fuente de verdad: el historial viaja en cada turno y no hay sesión del proveedor.

### 4.2 Turno de voz

1. El cliente graba un segmento (o detecta fin de habla) y lo envía a `POST /api/v1/voice/transcribe`.
2. El adapter STT devuelve texto + idioma detectado.
3. El texto entra al mismo caso de uso que el chat de texto: **un solo camino de conversación**.
4. La respuesta se sintetiza con TTS (Piper) en `POST /api/v1/voice/speech` y el cliente la reproduce; el texto se muestra siempre como alternativa accesible.

### 4.3 Intérprete en tiempo real

Flujo distinto del chat. Segmentos continuos: STT → traducción → TTS opcional, con historial temporal de fragmentos.
Requiere canal persistente (WebSocket) y no reutiliza el turno de conversación.

## 5. Asuntos transversales

- **Errores:** un único sobre de error (`docs/api-contract.md` §4). Los errores de dominio se traducen en `api/`, no se filtran excepciones de proveedores.
- **Logging:** estructurado, con `request_id` y `conversation_id`; sin contenido de audio ni texto del usuario en logs por defecto (privacidad).
- **Configuración:** variables de entorno tipadas en `core/config.py`; nada de secretos en el repo.
- **Límites:** duración y tamaño máximo de audio, timeout por proveedor, presupuesto de tokens por turno. Fallar rápido y con mensaje claro.
- **Idempotencia:** reintentos de envío de mensajes no deben duplicar turnos; usar clave de idempotencia del cliente.
- **Cancelación:** si el usuario corta la reproducción o abandona el turno, se cancela la llamada al proveedor.

## 6. Escalabilidad (lo que sí importa)

- API sin estado → N réplicas detrás de un balanceador.
- TTS y transcripciones largas: trabajo en cola con resultado por polling o streaming, nunca bloqueando el request.
- Presupuesto y caché: respuestas de TTS por (texto, voz, velocidad) son cacheables; el chat no.
- Base de datos: índices por `language_id` y por `conversation_id`; paginación por cursor en historiales.
- Métricas mínimas: latencia por proveedor (STT, LLM, TTS), tasa de error, costo por turno.

## 7. Riesgos técnicos conocidos

| Riesgo | Impacto | Mitigación inicial |
|---|---|---|
| Latencia de voz percibida | Sensación de producto roto | Streaming por frases y estados visibles; medir antes de optimizar |
| Piper en CPU saturada | Turnos lentos con varios usuarios | Cola + límite de concurrencia; evaluar workers dedicados |
| STT con acentos o ruido | Transcripciones pobres | Mostrar y permitir editar el texto antes de enviar |
| Costo por turno | Producto inviable a escala | Presupuesto por sesión y métricas de costo desde el inicio |
| Acoplamiento al proveedor | Migración dolorosa | Puertos + adapters; ningún SDK fuera de `adapters/` |

## 8. Fuera de alcance por ahora

Microservicios, Kubernetes, multi-tenant con facturación, colaboración en tiempo real, modelos locales en el navegador.
