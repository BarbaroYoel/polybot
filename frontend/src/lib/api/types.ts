/**
 * Contract types (docs/api-contract.md §2). They mirror the JSON field by field: snake_case,
 * string timestamps and nullable fields exactly as the API returns them.
 *
 * The UI keeps its own camelCase types in `src/lib/types.ts`; the translation happens in the
 * feature that consumes the data, never here.
 */

export type CefrLevel = "A1" | "A2" | "B1" | "B2" | "C1" | "C2";

export type ConversationMode = "free" | "guided" | "roleplay" | "exercise" | "live_voice";

export type MessageAuthor = "tutor" | "user";

export type MessageStatus = "sent" | "streaming" | "error";

export interface WeeklyGoal {
  conversations: number;
  minutes: number;
}

/** `GET /languages` returns a plain array of these, oldest first. */
export interface LanguageProfile {
  id: string;
  code: string;
  name: string;
  level: CefrLevel;
  explanation_language: string;
  is_active: boolean;
  archived: boolean;
  weekly_goal: WeeklyGoal;
  created_at: string;
}

export interface Conversation {
  id: string;
  language_id: string;
  mode: ConversationMode;
  title: string;
  message_count: number;
  last_message_at: string | null;
  created_at: string;
}

/**
 * One correction of the closing turn (F3 S7): what the student wrote, the fixed version and why.
 */
export interface Correction {
  original: string;
  corrected: string;
  explanation: string;
}

/** One suggested term of the closing turn (F3 S7): the word, its translation and a short note. */
export interface VocabularyItem {
  term: string;
  translation: string;
  note: string | null;
}

/**
 * Feedback the closing turn produced for one user message. `GET /conversations/{id}` returns it on
 * every user message so the cards survive a reload (F3 S7).
 */
export interface MessageFeedback {
  corrections: Correction[];
  vocabulary: VocabularyItem[];
}

/**
 * Practice block of a tutor turn (ADR-020, contract §2). The API only sends what the client needs
 * to render it: the accepted answers of a drill stay on the server.
 */
export interface PhraseBlock {
  id: string;
  kind: "phrase";
  text: string;
}

export interface DrillBlock {
  id: string;
  kind: "drill";
  prompt: string;
}

export type TurnBlock = PhraseBlock | DrillBlock;

/** Verdict of one drill: `expected` only travels after a miss (contract §3). */
export interface DrillAnswer {
  correct: boolean;
  expected: string | null;
  explanation: string;
}

/**
 * Note: docs/api-contract.md §2 lists `audio_url` on messages, but the running API does not send
 * it (voice arrives in F4). The type follows the payload, not the field that does not exist yet.
 *
 * `feedback` is optional on purpose: the API adds it with the closing turn (F3 S7) and the client
 * must keep working while a payload does not carry it yet.
 */
export interface Message {
  id: string;
  conversation_id: string;
  author: MessageAuthor;
  content: string;
  translation: string | null;
  status: MessageStatus;
  created_at: string;
  feedback?: MessageFeedback | null;
  /** Practice blocks of a tutor turn (ADR-020); `[]` or absent means the turn has none. */
  blocks?: TurnBlock[];
}

/** Payload of the `token` event: one text delta of the tutor message (contract §3). */
export interface TurnTokenEvent {
  message_id: string;
  delta: string;
}

/** Payload of the `blocks` event: practice blocks of the tutor message that just ended (ADR-020). */
export interface TurnBlocksEvent {
  message_id: string;
  items: TurnBlock[];
}

/** Payload of the `correction` event: corrections of the user message that opened the turn. */
export interface TurnCorrectionsEvent {
  message_id: string;
  items: Correction[];
}

/** Payload of the `vocabulary` event: suggested terms of the user message that opened the turn. */
export interface TurnVocabularyEvent {
  message_id: string;
  items: VocabularyItem[];
}

export interface ConversationPage {
  items: Conversation[];
  next_cursor: string | null;
}

export interface MessagePage {
  items: Message[];
  next_cursor: string | null;
}

export interface ConversationDetail extends Conversation {
  messages: MessagePage;
}

// F5 — lessons and study plans (docs/api-contract.md §3 "Aprendizaje").

/** State of a lesson or of a plan session, always derived from the stored attempts (F5 S5). */
export type LessonStatus = "pending" | "in_progress" | "completed";

/** The unit kinds of desing.md §6.2, in catalog order. */
export type LessonUnitKind =
  | "vocabulary"
  | "grammar"
  | "pronunciation"
  | "listening"
  | "situational";

/** One lesson as the catalog lists it. The accepted answers never reach the client (F5 S8). */
export interface LessonSummary {
  id: string;
  unit_id: string;
  title: string;
  difficulty: CefrLevel;
  estimated_minutes: number;
  position: number;
  status: LessonStatus;
}

export interface LessonUnit {
  id: string;
  kind: LessonUnitKind;
  title: string;
  description: string;
  position: number;
  lessons: LessonSummary[];
}

/** `GET /lessons?language_id=`: units of one language plus the lesson «Continuar aprendiendo». */
export interface LessonCatalog {
  language_id: string;
  language_name: string;
  level: CefrLevel;
  next_lesson: LessonSummary | null;
  units: LessonUnit[];
}

/** How the student answers an exercise (ADR-021): typing the phrase, or picking one option. */
export type LessonExerciseKind = "writing" | "choice";

export interface LessonExercise {
  id: string;
  position: number;
  prompt: string;
  kind: LessonExerciseKind;
  /** Options of a `choice`; empty for a `writing` one. The right answer is never marked. */
  options: string[];
}

/** `GET /lessons/{id}`: the lesson text and its prompts, never the accepted answers. */
export interface LessonDetail {
  id: string;
  language_id: string;
  unit_id: string;
  unit_title: string;
  unit_kind: LessonUnitKind;
  title: string;
  difficulty: CefrLevel;
  estimated_minutes: number;
  intro: string;
  exercises: LessonExercise[];
}

/** One wrong answer of a submitted attempt, with what was expected and why (F5 S2). */
export interface LessonMistake {
  exercise_id: string;
  prompt: string;
  answer: string;
  expected: string;
  explanation: string;
}

export interface LessonTerm {
  term: string;
  translation: string;
  note: string | null;
}

/** `POST /lessons/{id}/submit`: the graded attempt, its mistakes and the next recommendation. */
export interface LessonResult {
  attempt_id: string;
  lesson_id: string;
  correct: number;
  total: number;
  completed: boolean;
  mistakes: LessonMistake[];
  vocabulary: LessonTerm[];
  feedback: string | null;
  next_lesson: LessonSummary | null;
}

export type PlanSessionState = "pending" | "in_progress" | "completed";

/** One session of the schedule. Its state is read-only: no endpoint changes it by hand. */
export interface PlanSession {
  id: string;
  week: number;
  position: number;
  lesson_id: string;
  lesson_title: string;
  status: PlanSessionState;
}

/** A study plan with its weekly schedule and the session «Continuar plan» opens. */
export interface StudyPlan {
  id: string;
  language_id: string;
  goal: string;
  frequency: number;
  daily_minutes: number;
  weeks: number;
  created_at: string;
  adjusted_at: string | null;
  next_session: PlanSession | null;
  sessions: PlanSession[];
}

/** `GET /plans?language_id=`: a language without a plan answers `plan: null`, not an error. */
export interface LanguagePlan {
  language_id: string;
  plan: StudyPlan | null;
}

// F6 — progress (docs/api-contract.md §3 "El progreso", ADR-018).

/** The five skills of desing.md §6.5, always returned in this order. */
export type ProgressSkillId =
  | "conversation"
  | "writing"
  | "vocabulary"
  | "reading"
  | "listening";

/**
 * Activity recorded for one skill. `available: false` means the product does not record that
 * signal yet, so `count` is `null` and the UI must not show it as a measured zero (F6 S2).
 */
export interface ProgressSkill {
  id: ProgressSkillId;
  available: boolean;
  count: number | null;
  last_at: string | null;
}

/**
 * One recurring mistake. `correction` comes from the closing turn of a conversation and has no
 * prompt; `lesson` comes from a wrong answer of a lesson attempt (F6 S3).
 */
export interface FrequentError {
  kind: "correction" | "lesson";
  prompt: string | null;
  original: string;
  expected: string;
  count: number;
  last_at: string;
}

/**
 * One practice of the history. A `lesson` carries `correct`/`total`; a `conversation` carries
 * `message_count`. The nullable fields of the other kind stay `null` (F6 S4).
 */
export interface ProgressHistoryEntry {
  kind: "lesson" | "conversation";
  id: string;
  title: string;
  at: string;
  correct: number | null;
  total: number | null;
  message_count: number | null;
}

/** Weekly goal of the active language: conversations with a message since Monday 00:00 of `tz`. */
export interface WeeklyGoalProgress {
  conversations: number;
  target: number;
}

/** Active-language totals. They count recorded activity, not mastery (ADR-018). */
export interface ProgressSummary {
  /** The stored level of the profile, not a calculated measurement (ADR-008). */
  level: CefrLevel;
  lessons_completed: number;
  lessons_total: number;
  conversations: number;
  weekly_goal: WeeklyGoalProgress;
}

/** Language block of `GET /progress`: minimal profile, enough to label the screen. */
export interface ProgressLanguage {
  id: string;
  code: string;
  name: string;
  level: CefrLevel;
}

/**
 * `GET /progress?language_id=&tz=`: everything is derived from stored conversations, attempts,
 * corrections and vocabulary. No minutes: v0 does not record duration (F6, ADR-018).
 */
export interface Progress {
  language: ProgressLanguage;
  summary: ProgressSummary;
  skills: ProgressSkill[];
  frequent_errors: FrequentError[];
  history: ProgressHistoryEntry[];
}
