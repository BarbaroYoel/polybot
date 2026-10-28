/**
 * Live interpreter WebSocket (F7, ADR-022).
 *
 * The client sends raw PCM frames and the server answers JSON events. The URL is derived from the
 * same `API_BASE_URL` as the HTTP client, changing the scheme to `ws`/`wss`, so the Vite proxy and
 * Codespaces work without a second configuration.
 */

import { API_BASE_URL } from "./client";

export interface InterpreterReady {
  type: "ready";
  format: string;
  sample_rate: number;
  source: string | null;
  target: string;
}

export interface InterpreterPartial {
  type: "partial";
  seq: number;
  text: string;
  pending: string;
  language: string | null;
  received_ms: number;
}

export interface InterpreterPartialTranslation {
  type: "partial_translation";
  seq: number;
  text: string;
  target: string;
}

export interface InterpreterSegment {
  type: "segment";
  id: string;
  text: string;
  language: string | null;
  start_ms: number;
  end_ms: number;
}

export interface InterpreterTranslation {
  type: "translation";
  segment_id: string;
  text: string;
  target: string;
}

export interface InterpreterError {
  type: "error";
  error: {
    code: string;
    message: string;
    details: unknown;
    request_id: string;
  };
}

export type InterpreterEvent =
  | InterpreterReady
  | InterpreterPartial
  | InterpreterPartialTranslation
  | InterpreterSegment
  | InterpreterTranslation
  | InterpreterError;

/** `ws(s)://…/api/v1/voice/interpret?source=&target=`. */
export function interpreterUrl(source: string | null, target: string): string {
  const url = new URL(API_BASE_URL, window.location.href);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.pathname = `${url.pathname.replace(/\/+$/, "")}/voice/interpret`;
  const params = new URLSearchParams({ target });
  if (source) params.set("source", source);
  url.search = params.toString();
  return url.toString();
}

export function openInterpreter(source: string | null, target: string): WebSocket {
  return new WebSocket(interpreterUrl(source, target));
}

/** Parse one server frame; a malformed frame is ignored instead of breaking the session. */
export function parseInterpreterEvent(raw: string): InterpreterEvent | null {
  try {
    const value = JSON.parse(raw) as { type?: unknown };
    if (!value || typeof value.type !== "string") return null;
    return value as InterpreterEvent;
  } catch {
    return null;
  }
}
