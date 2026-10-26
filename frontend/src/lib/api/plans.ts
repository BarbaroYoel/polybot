/**
 * `/plans` calls (docs/api-contract.md §3 "Aprendizaje", F5 S3, S4).
 *
 * One plan per language. The schedule and every session state come from the server; the only
 * write that recalculates it is the explicit adjustment the user asks for.
 */

import { apiFetch, requestBody } from "./client";
import type { LanguagePlan, StudyPlan } from "./types";

export interface CreatePlanInput {
  language_id: string;
  goal: string;
  /** Sessions per week, 1–7. */
  frequency: number;
  /** Minutes the user can give each day, 5–120. */
  daily_minutes: number;
}

/** The goal is not adjustable: only these two values can change after creation. */
export interface AdjustPlanInput {
  frequency?: number;
  daily_minutes?: number;
}

/** The plan of one language, or `plan: null` when it has none. An unknown language is a 404. */
export function getPlan(languageId: string): Promise<LanguagePlan> {
  return apiFetch<LanguagePlan>(`/plans?language_id=${encodeURIComponent(languageId)}`);
}

/** Creates the plan and its deterministic schedule. A language with a plan is a 409. */
export function createPlan(input: CreatePlanInput): Promise<StudyPlan> {
  return apiFetch<StudyPlan>("/plans", requestBody("POST", input));
}

/** Explicit adjustment: recalculates the schedule and marks `adjusted_at`. */
export function adjustPlan(planId: string, patch: AdjustPlanInput): Promise<StudyPlan> {
  return apiFetch<StudyPlan>(
    `/plans/${encodeURIComponent(planId)}`,
    requestBody("PATCH", patch),
  );
}
