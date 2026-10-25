/** `/voice` calls (docs/api-contract.md §3 «Voz»; F4). */

import { apiFetch } from "./client";

/** What the engine heard, in the language it used, and how long the clip was. */
export interface Transcription {
  text: string;
  /** The engine's own answer; `null` when it did not report one. */
  language_detected: string | null;
  duration_ms: number;
}

/**
 * Send the recorded clip. `multipart/form-data` is built by the browser: setting `Content-Type` by
 * hand would drop the boundary and the request would fail.
 */
export function transcribe(audio: Blob, languageCode?: string): Promise<Transcription> {
  const body = new FormData();
  body.append("audio", audio, "clip.wav");
  if (languageCode) body.append("language_code", languageCode);
  return apiFetch<Transcription>("/voice/transcribe", { method: "POST", body });
}
