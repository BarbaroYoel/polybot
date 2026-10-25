/**
 * Translation endpoints (docs/api-contract.md §3; ADR-014).
 *
 * Two different jobs with two different lifetimes: a fragment is translated and forgotten, a whole
 * message is translated and stored, so the bubble shows it again after a reload.
 */

import { apiFetch, requestBody } from "./client";
import type { Message } from "./types";

export interface TranslateResult {
  translation: string;
  /** The source that was used, or `null` when the caller did not send one. */
  detected_source: string | null;
}

/** Translate a selected fragment: nothing is stored (S2). */
export function translateText(payload: {
  text: string;
  source?: string;
  target: string;
}): Promise<TranslateResult> {
  return apiFetch<TranslateResult>("/translate", requestBody("POST", payload));
}

/**
 * Translate the whole message and store it. The API answers the stored message, and a second call
 * reuses the translation instead of asking the provider again (S2, S4).
 */
export function translateMessage(conversationId: string, messageId: string): Promise<Message> {
  return apiFetch<Message>(
    `/conversations/${encodeURIComponent(conversationId)}/messages/${encodeURIComponent(
      messageId,
    )}/translation`,
    { method: "POST" },
  );
}
