/**
 * `/progress` calls (docs/api-contract.md §3 "El progreso", F6 S6, S7).
 *
 * The server derives every number from stored conversations, lesson attempts, corrections and
 * vocabulary. The client never estimates duration, adds minutes or writes progress.
 */

import { apiFetch } from "./client";
import type { Progress } from "./types";

/**
 * Progress of one language. `tz` is an IANA zone (for example `America/Argentina/Buenos_Aires`)
 * and decides when the weekly goal's Monday 00:00 starts; the API defaults to `UTC`.
 * An unknown language is a 404 `language_not_found`, not an empty screen.
 */
export function getProgress(languageId: string, tz?: string): Promise<Progress> {
  const params = [`language_id=${encodeURIComponent(languageId)}`];
  if (tz) params.push(`tz=${encodeURIComponent(tz)}`);
  return apiFetch<Progress>(`/progress?${params.join("&")}`);
}
