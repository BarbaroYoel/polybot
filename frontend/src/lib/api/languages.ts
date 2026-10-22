/**
 * `/languages` calls (docs/api-contract.md §3 "Idiomas").
 *
 * Inputs mirror the wire format (snake_case) because they are the contract's own terms, e.g.
 * `updateLanguage(id, { is_active: true })`. Arguments that the UI names differently
 * (`languageId`) stay camelCase in `conversations.ts`.
 */

import { apiFetch, requestBody } from "./client";
import type { CefrLevel, LanguageProfile, WeeklyGoal } from "./types";

export interface CreateLanguageInput {
  code: string;
  name: string;
  level: CefrLevel;
  explanation_language?: string;
  weekly_goal?: WeeklyGoal;
}

export interface UpdateLanguageInput {
  level?: CefrLevel;
  weekly_goal?: WeeklyGoal;
  is_active?: boolean;
}

/** Non-archived languages, oldest first. The API answers an array, not a page. */
export function listLanguages(): Promise<LanguageProfile[]> {
  return apiFetch<LanguageProfile[]>("/languages");
}

/** The new language is created inactive; activating it is a second, explicit action. */
export function createLanguage(input: CreateLanguageInput): Promise<LanguageProfile> {
  return apiFetch<LanguageProfile>("/languages", requestBody("POST", input));
}

/** Activating one language deactivates the previous one on the server. */
export function updateLanguage(
  id: string,
  patch: UpdateLanguageInput,
): Promise<LanguageProfile> {
  return apiFetch<LanguageProfile>(
    `/languages/${encodeURIComponent(id)}`,
    requestBody("PATCH", patch),
  );
}

/** Soft delete: `204`. Archiving the active (or the last) language is a `409` from the API. */
export async function archiveLanguage(id: string): Promise<void> {
  await apiFetch<void>(`/languages/${encodeURIComponent(id)}`, { method: "DELETE" });
}
