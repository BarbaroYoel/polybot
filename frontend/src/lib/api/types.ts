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
}

/** Payload of the `token` event: one text delta of the tutor message (contract §3). */
export interface TurnTokenEvent {
  message_id: string;
  delta: string;
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
