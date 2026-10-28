/**
 * Answering one drill of a tutor turn (docs/api-contract.md §3 "Bloques de práctica"; ADR-020).
 *
 * The API grades the answer with the same deterministic rules as a lesson and reveals the expected
 * answer only after a miss. Nothing is stored: the client keeps the verdict in memory for the life
 * of the screen, and a reload asks the question again.
 */

import { apiFetch, requestBody } from "./client";
import type { DrillAnswer } from "./types";

export function answerBlock(
  conversationId: string,
  messageId: string,
  blockId: string,
  answer: string,
): Promise<DrillAnswer> {
  const request = requestBody("POST", { answer });
  return apiFetch<DrillAnswer>(
    `/conversations/${encodeURIComponent(conversationId)}` +
      `/messages/${encodeURIComponent(messageId)}` +
      `/blocks/${encodeURIComponent(blockId)}/answers`,
    request,
  );
}
