/**
 * Minimal HTTP client for the Polybot API (docs/api-contract.md).
 *
 * No dependency is added on purpose (AGENTS.md §3 and §5): `fetch` plus the contract's error
 * envelope is everything the PWA needs in v0.
 */

const DEFAULT_BASE_URL = "http://localhost:8000/api/v1";

/** Base URL of the API. Overridable with `VITE_API_BASE_URL` (typed in `src/vite-env.d.ts`). */
export const API_BASE_URL = normalizeBaseUrl(import.meta.env.VITE_API_BASE_URL);

function normalizeBaseUrl(value: string | undefined): string {
  const trimmed = value?.trim().replace(/\/+$/, "") ?? "";
  return trimmed || DEFAULT_BASE_URL;
}

export interface ApiErrorInit {
  code: string;
  message: string;
  status: number;
  requestId?: string;
  details?: unknown;
}

/**
 * An error shaped by the contract envelope (docs/api-contract.md §4). `message` is the Spanish
 * text written for the user and can be shown as-is; `code` is the stable English identifier.
 */
export class ApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly requestId: string;
  readonly details: unknown;

  constructor({ code, message, status, requestId = "", details = null }: ApiErrorInit) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.requestId = requestId;
    this.details = details;
  }
}

export function isApiError(value: unknown): value is ApiError {
  return value instanceof ApiError;
}

/**
 * Codes this client produces itself. They are not part of the contract because the API never
 * answers with them: one means the request never arrived, the other that the answer was not JSON.
 */
const NETWORK_ERROR = "network_error";
const UNEXPECTED_RESPONSE = "unexpected_response";
const UNEXPECTED_LOCAL_ERROR = "unexpected_error";

/** Shown when there is no API `message` to show: it says what the user can do next. */
export const GENERIC_ACTION_ERROR =
  "No se pudo completar la acción. Vuelve a intentar en unos segundos.";

const NETWORK_ERROR_MESSAGE =
  "No pudimos conectar con el servidor. Revisa tu conexión y vuelve a intentar; en local, confirma que la API esté corriendo.";

const UNEXPECTED_RESPONSE_MESSAGE =
  "El servidor respondió con un error inesperado. Vuelve a intentar en unos segundos.";

interface ErrorEnvelope {
  error?: {
    code?: unknown;
    message?: unknown;
    details?: unknown;
    request_id?: unknown;
  };
}

/**
 * Read the contract envelope. When the body is not an envelope (proxy error page, empty body)
 * the status is kept and a local code plus an actionable Spanish message are used instead.
 */
async function readError(response: Response): Promise<ApiError> {
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

/**
 * `apiFetch<T>("/languages")` resolves the parsed body or throws an `ApiError`. `204` responses
 * (archive, delete) resolve `undefined`, so callers ask for `void`.
 */
export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers });
  } catch {
    throw new ApiError({ code: NETWORK_ERROR, message: NETWORK_ERROR_MESSAGE, status: 0 });
  }

  if (!response.ok) {
    throw await readError(response);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  try {
    return (await response.json()) as T;
  } catch {
    throw new ApiError({
      code: UNEXPECTED_RESPONSE,
      message: UNEXPECTED_RESPONSE_MESSAGE,
      status: response.status,
    });
  }
}

/** JSON write options: v0 only accepts JSON bodies (docs/api-contract.md §1). */
export function requestBody(method: "POST" | "PATCH", body: unknown): RequestInit {
  return {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
}

/** Normalize any thrown value into the one error type the UI knows how to show. */
export function toApiError(error: unknown): ApiError {
  if (isApiError(error)) return error;
  return new ApiError({
    code: UNEXPECTED_LOCAL_ERROR,
    message: GENERIC_ACTION_ERROR,
    status: 0,
  });
}

/** The API `message` is already user-facing Spanish; anything else gets the generic fallback. */
export function errorMessage(error: unknown, fallback = GENERIC_ACTION_ERROR): string {
  if (isApiError(error) && error.message.trim()) return error.message;
  return fallback;
}
