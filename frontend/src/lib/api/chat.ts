/**
 * The tutor turn: send the user message and stream the reply
 * (docs/api-contract.md §3 "El stream del turno"; F3 S9).
 *
 * No dependency is added on purpose (AGENTS.md §3): `fetch` plus a `ReadableStream` reader is all
 * the PWA needs. `EventSource` is deliberately not used — it cannot send the `Idempotency-Key`
 * header, nor abort the request, and S6 needs the cut to close the server-side stream.
 */

import { API_BASE_URL, ApiError, apiFetch, requestBody } from "./client";
import type { Correction, Message, TurnTokenEvent, VocabularyItem } from "./types";

/**
 * Codes this module produces itself, mirroring the ones `client.ts` keeps private. They are not
 * part of the contract: the API never answers with them.
 */
const NETWORK_ERROR = "network_error";
const UNEXPECTED_RESPONSE = "unexpected_response";
const STREAM_INCOMPLETE = "stream_incomplete";

const NETWORK_ERROR_MESSAGE =
  "No pudimos conectar con el servidor. Revisa tu conexión y vuelve a intentar; en local, confirma que la API esté corriendo.";

const UNEXPECTED_RESPONSE_MESSAGE =
  "El servidor respondió con un error inesperado. Vuelve a intentar en unos segundos.";

const STREAM_INCOMPLETE_MESSAGE =
  "La respuesta se cortó antes de terminar. Reintentar retoma el turno.";

/** `error` events carry no HTTP status; the contract maps these codes to 502 and 504 (§3, §4). */
const STREAM_ERROR_STATUS: Record<string, number> = {
  llm_unavailable: 502,
  llm_timeout: 504,
};

export interface SendMessageOptions {
  /** Aborts the request when the screen unmounts. */
  signal?: AbortSignal;
}

/**
 * Persist the user message and open its turn (S4).
 *
 * `idempotencyKey` must be reused while retrying the same turn: the API resolves a repeated key to
 * the message it already stored instead of creating a second turn (contract §1 and §3).
 */
export function sendMessage(
  conversationId: string,
  content: string,
  idempotencyKey: string,
  options: SendMessageOptions = {},
): Promise<Message> {
  const request = requestBody("POST", { content });
  return apiFetch<Message>(`/conversations/${encodeURIComponent(conversationId)}/messages`, {
    ...request,
    headers: {
      ...(request.headers as Record<string, string>),
      "Idempotency-Key": idempotencyKey,
    },
    signal: options.signal,
  });
}

/**
 * What the screen does with the events it understands. Unknown events are ignored, so the contract
 * can grow (`correction`, `vocabulary` and anything after them) without breaking this client.
 */
export interface TurnStreamHandlers {
  onToken?: (event: TurnTokenEvent) => void;
  /** The authoritative tutor message, already persisted as `sent` (contract §3). */
  onMessageEnd?: (message: Message) => void;
  onCorrections?: (messageId: string, items: Correction[]) => void;
  onVocabulary?: (messageId: string, items: VocabularyItem[]) => void;
}

/** One parsed SSE block: the `event` name and its `data` payload (contract §3). */
interface SseEvent {
  name: string;
  data: string;
}

interface ErrorEnvelope {
  error?: {
    code?: unknown;
    message?: unknown;
    details?: unknown;
    request_id?: unknown;
  };
}

/**
 * Incremental parser for the contract's SSE. Decoded chunks arrive in any size: complete lines are
 * consumed as they appear and a block is emitted when a blank line closes it. `data` may repeat and
 * `:` starts a comment (a keep-alive the contract allows but does not require).
 */
function createSseParser(onEvent: (event: SseEvent) => void) {
  let buffer = "";
  let name = "message";
  let data: string[] = [];

  const dispatch = () => {
    if (data.length > 0) onEvent({ name, data: data.join("\n") });
    name = "message";
    data = [];
  };

  const consumeLine = (line: string) => {
    if (line === "") {
      dispatch();
      return;
    }
    if (line.startsWith(":")) return;

    const separator = line.indexOf(":");
    const field = separator === -1 ? line : line.slice(0, separator);
    const raw = separator === -1 ? "" : line.slice(separator + 1);
    const value = raw.startsWith(" ") ? raw.slice(1) : raw;

    if (field === "event") name = value;
    else if (field === "data") data.push(value);
    // `id` and `retry` are not part of the contract: ignored on purpose.
  };

  return {
    /** Feed one decoded chunk; whatever is not a complete line yet waits for the next one. */
    push(chunk: string) {
      buffer += chunk;
      let end = buffer.indexOf("\n");
      while (end !== -1) {
        const line = buffer.slice(0, end).replace(/\r$/, "");
        buffer = buffer.slice(end + 1);
        consumeLine(line);
        end = buffer.indexOf("\n");
      }
    },
    /** Close the last block when the server did not end it with a blank line. */
    flush() {
      if (buffer) {
        consumeLine(buffer.replace(/\r$/, ""));
        buffer = "";
      }
      dispatch();
    },
  };
}

function parsePayload<T>(data: string): T | null {
  try {
    return JSON.parse(data) as T;
  } catch {
    return null;
  }
}

function unexpectedStream(): ApiError {
  return new ApiError({
    code: UNEXPECTED_RESPONSE,
    message: UNEXPECTED_RESPONSE_MESSAGE,
    status: 0,
  });
}

/**
 * The pre-stream failures (404 `message_not_found`, 400 `invalid_turn_message`, …) still use the
 * JSON envelope of docs/api-contract.md §4. `client.ts` keeps that read private and is outside this
 * task's edit surface, so the same read lives here for the `fetch` this module owns.
 */
async function readStreamError(response: Response): Promise<ApiError> {
  let envelope: ErrorEnvelope | null = null;
  try {
    envelope = (await response.json()) as ErrorEnvelope;
  } catch {
    envelope = null;
  }

  const error = envelope?.error;
  if (typeof error?.code === "string" && typeof error?.message === "string") {
    return new ApiError({
      code: error.code,
      message: error.message,
      status: response.status,
      requestId: typeof error.request_id === "string" ? error.request_id : "",
      details: error.details,
    });
  }

  return new ApiError({
    code: UNEXPECTED_RESPONSE,
    message: UNEXPECTED_RESPONSE_MESSAGE,
    status: response.status,
  });
}

function readEventError(payload: ErrorEnvelope | null): ApiError {
  const error = payload?.error;
  if (typeof error?.code === "string" && typeof error?.message === "string") {
    return new ApiError({
      code: error.code,
      message: error.message,
      status: STREAM_ERROR_STATUS[error.code] ?? 0,
      requestId: typeof error.request_id === "string" ? error.request_id : "",
      details: error.details,
    });
  }
  return unexpectedStream();
}

function handleEvent(event: SseEvent, handlers: TurnStreamHandlers): void {
  switch (event.name) {
    case "token": {
      const payload = parsePayload<{ message_id?: unknown; delta?: unknown }>(event.data);
      if (typeof payload?.message_id !== "string" || typeof payload.delta !== "string") {
        throw unexpectedStream();
      }
      handlers.onToken?.({ message_id: payload.message_id, delta: payload.delta });
      return;
    }
    case "message_end": {
      const message = parsePayload<Message>(event.data);
      if (!message || typeof message.id !== "string") throw unexpectedStream();
      handlers.onMessageEnd?.(message);
      return;
    }
    case "correction": {
      const payload = parsePayload<{ message_id?: unknown; items?: unknown }>(event.data);
      if (typeof payload?.message_id !== "string" || !Array.isArray(payload.items)) {
        throw unexpectedStream();
      }
      handlers.onCorrections?.(payload.message_id, payload.items as Correction[]);
      return;
    }
    case "vocabulary": {
      const payload = parsePayload<{ message_id?: unknown; items?: unknown }>(event.data);
      if (typeof payload?.message_id !== "string" || !Array.isArray(payload.items)) {
        throw unexpectedStream();
      }
      handlers.onVocabulary?.(payload.message_id, payload.items as VocabularyItem[]);
      return;
    }
    case "error":
      throw readEventError(parsePayload<ErrorEnvelope>(event.data));
    default:
      // A name this client does not know yet is not a failure: the contract can add events.
      return;
  }
}

/**
 * Stream one turn (S5) and resolve when the server closes the stream after `message_end`.
 *
 * Throws an `ApiError` when the request fails, when the server sends `error` (contract §4), or when
 * the stream closes without `message_end`. Aborting `signal` closes the HTTP stream — which cancels
 * the provider on the server (S6) — and rethrows the abort as-is: a cut by the user is not a UI
 * error, so the caller decides how to show the partial text.
 */
export async function streamTurn(
  conversationId: string,
  messageId: string,
  handlers: TurnStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const path =
    `/conversations/${encodeURIComponent(conversationId)}/stream` +
    `?message_id=${encodeURIComponent(messageId)}`;

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      headers: { Accept: "text/event-stream" },
      signal,
    });
  } catch (error) {
    if (signal?.aborted) throw error;
    throw new ApiError({
      code: NETWORK_ERROR,
      message: NETWORK_ERROR_MESSAGE,
      status: 0,
    });
  }

  if (!response.ok) throw await readStreamError(response);

  const body = response.body;
  if (!body) throw unexpectedStream();

  const reader = body.getReader();
  const decoder = new TextDecoder();
  let ended = false;

  const parser = createSseParser((event) => {
    if (event.name === "message_end") ended = true;
    handleEvent(event, handlers);
  });

  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      parser.push(decoder.decode(value, { stream: true }));
    }
    // A multi-byte character or a block can be split at the very end of the stream.
    parser.push(decoder.decode());
    parser.flush();
  } finally {
    // Leaving early (provider error, abort) closes the stream so the server cancels the turn (S6).
    void reader.cancel().catch(() => undefined);
  }

  if (!ended) {
    throw new ApiError({
      code: STREAM_INCOMPLETE,
      message: STREAM_INCOMPLETE_MESSAGE,
      status: 0,
    });
  }
}
