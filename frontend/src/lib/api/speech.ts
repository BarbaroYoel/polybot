/** `/voice/speech`: what the tutor says out loud (docs/api-contract.md §3 «Voz»; ADR-016). */

import { API_BASE_URL, ApiError } from "./client";

export interface SpeechClip {
  blob: Blob;
  /** Content-addressed id: the same text, voice and speed always answer the same one. */
  id: string | null;
}

export interface SynthesizeOptions {
  text: string;
  languageCode: string;
  speed?: number;
  signal?: AbortSignal;
}

/**
 * Ask the backend for a clip. The answer is audio, not JSON, so this cannot go through `apiFetch`:
 * the error envelope is read here by hand, and the body stays a `Blob`.
 */
export async function synthesizeSpeech({
  text,
  languageCode,
  speed = 1,
  signal,
}: SynthesizeOptions): Promise<SpeechClip> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/voice/speech`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "audio/wav" },
      body: JSON.stringify({ text, language_code: languageCode, speed }),
      signal,
    });
  } catch {
    throw new ApiError({
      code: "network_error",
      message:
        "No pudimos conectar con el servidor. Revisá tu conexión y volvé a intentar; en local, confirmá que la API esté corriendo.",
      status: 0,
    });
  }

  if (!response.ok) throw await readEnvelope(response);
  return { blob: await response.blob(), id: response.headers.get("X-Speech-Id") };
}

/** The contract envelope, or a generic failure with the status of the response. */
async function readEnvelope(response: Response): Promise<ApiError> {
  try {
    const body = (await response.json()) as {
      error?: { code?: string; message?: string; request_id?: string; details?: unknown };
    };
    if (body.error?.message) {
      return new ApiError({
        code: body.error.code ?? "unexpected_response",
        message: body.error.message,
        status: response.status,
        requestId: body.error.request_id,
        details: body.error.details,
      });
    }
  } catch {
    // Not JSON: fall through to the generic message.
  }
  return new ApiError({
    code: "unexpected_response",
    message: "No pudimos generar el audio. Vuelve a intentar en unos segundos.",
    status: response.status,
  });
}
