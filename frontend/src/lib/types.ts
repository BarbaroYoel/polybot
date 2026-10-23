/**
 * UI view types. They stay camelCase and independent from the API: the mapping from the contract
 * types (`src/lib/api/types.ts`) happens in the feature that consumes the data.
 */

export type Author = "tutor" | "user";

/**
 * Turn states of the chat screen (F3 S9): `idle` is the screen before any send, `sending` is the
 * POST in flight, `streaming` is the open SSE stream, and `done | error` is how a turn ends. A turn
 * the user cuts ends as `done` with the partial text: a cancel is not a failure.
 */
export type TurnStatus = "idle" | "sending" | "streaming" | "done" | "error";

/** One correction of the user message, ready to render (F3 S7). */
export interface Correction {
  original: string;
  corrected: string;
  explanation: string;
}

/** One suggested term, ready to render (F3 S7). */
export interface VocabularyItem {
  term: string;
  translation: string;
  note?: string;
}

export interface Message {
  id: string;
  author: Author;
  content: string;
  timeLabel: string;
  translation?: string;
  hasAudio?: boolean;
  /** Tutor bubble waiting for its first token: shows «Pensando…» (desing.md §6.1.2). */
  pending?: boolean;
  /** Text left by a stream that failed or was cut: shown, not hidden. */
  incomplete?: boolean;
  /** Feedback of the closing turn; `undefined` when there is none or it has not arrived. */
  corrections?: Correction[];
  vocabulary?: VocabularyItem[];
}

/**
 * One turn opened from this screen: the optimistic user message, the tutor answer being streamed
 * and, for a failed turn, the error that offers «Reintentar».
 */
export interface ChatTurn {
  /** Stable turn id; reused as the `Idempotency-Key` when the same turn is retried (contract §1). */
  key: string;
  /** Server id of the user message; `null` while the POST is still in flight. */
  messageId: string | null;
  status: TurnStatus;
  user: Message;
  /** `null` when the turn failed before any tutor text existed. */
  tutor: Message | null;
  /** Spanish failure text of an `error` turn; `null` otherwise. */
  error: string | null;
}

/** One entry of the thread: a message or the retry block that closes a failed turn. */
export type ThreadItem =
  | { kind: "message"; message: Message }
  | { kind: "turn-error"; turnKey: string; message: string };
