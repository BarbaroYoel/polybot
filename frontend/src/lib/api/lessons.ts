/**
 * `/lessons` calls (docs/api-contract.md §3 "Aprendizaje", F5 S1, S2, S6).
 *
 * The catalog, the detail and the result are server-derived: the UI never guesses a lesson's
 * state, the accepted answers never reach the client, and every read is scoped to one language.
 */

import { apiFetch, requestBody } from "./client";
import type { LessonCatalog, LessonDetail, LessonResult } from "./types";

/** One exercise answer. The server refuses a submit that does not answer every exercise. */
export interface LessonAnswerInput {
  exercise_id: string;
  answer: string;
}

/** Catalog and next lesson of one language. An unknown language is a 404 `language_not_found`. */
export function getLessonCatalog(languageId: string): Promise<LessonCatalog> {
  return apiFetch<LessonCatalog>(`/lessons?language_id=${encodeURIComponent(languageId)}`);
}

/** One lesson with its exercises. `languageId` guards a lesson of another language as a 404. */
export function getLesson(lessonId: string, languageId?: string): Promise<LessonDetail> {
  const query = languageId ? `?language_id=${encodeURIComponent(languageId)}` : "";
  return apiFetch<LessonDetail>(`/lessons/${encodeURIComponent(lessonId)}${query}`);
}

/** Grades a finished lesson and stores the attempt. */
export function submitLesson(
  lessonId: string,
  answers: LessonAnswerInput[],
): Promise<LessonResult> {
  return apiFetch<LessonResult>(
    `/lessons/${encodeURIComponent(lessonId)}/submit`,
    requestBody("POST", { answers }),
  );
}
