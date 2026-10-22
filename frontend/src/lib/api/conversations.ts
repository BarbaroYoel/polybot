/**
 * `/conversations` calls (docs/api-contract.md §3 "Conversaciones y mensajes").
 *
 * Every conversation belongs to a language (AGENTS.md §3): the list requires `languageId` and
 * reading one conversation sends `languageId` as a guard, so another language's conversation
 * answers `404 conversation_not_found` instead of leaking into the active context.
 */

import { apiFetch, requestBody } from "./client";
import type {
  Conversation,
  ConversationDetail,
  ConversationMode,
  ConversationPage,
} from "./types";

export interface ListConversationsOptions {
  limit?: number;
  cursor?: string | null;
}

export interface GetConversationOptions {
  /** Activates the server-side guard: a conversation from another language is a `404`. */
  languageId?: string;
  messagesLimit?: number;
  messagesCursor?: string | null;
}

export interface CreateConversationInput {
  languageId: string;
  mode?: ConversationMode;
  title?: string;
}

/** Build the query string, skipping empty values so the API defaults apply. */
function query(params: Record<string, string | number | null | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    search.set(key, String(value));
  }
  const serialized = search.toString();
  return serialized ? `?${serialized}` : "";
}

/** History of one language, most recently active first. */
export function listConversations(
  languageId: string,
  options: ListConversationsOptions = {},
): Promise<ConversationPage> {
  return apiFetch<ConversationPage>(
    `/conversations${query({
      language_id: languageId,
      limit: options.limit,
      cursor: options.cursor,
    })}`,
  );
}

/** One conversation with its messages. Without `title` the server names it "Nueva conversación". */
export function getConversation(
  id: string,
  options: GetConversationOptions = {},
): Promise<ConversationDetail> {
  return apiFetch<ConversationDetail>(
    `/conversations/${encodeURIComponent(id)}${query({
      language_id: options.languageId,
      messages_limit: options.messagesLimit,
      messages_cursor: options.messagesCursor,
    })}`,
  );
}

export function createConversation(input: CreateConversationInput): Promise<Conversation> {
  return apiFetch<Conversation>(
    "/conversations",
    requestBody("POST", {
      language_id: input.languageId,
      mode: input.mode,
      title: input.title,
    }),
  );
}

export function renameConversation(id: string, title: string): Promise<Conversation> {
  return apiFetch<Conversation>(
    `/conversations/${encodeURIComponent(id)}`,
    requestBody("PATCH", { title }),
  );
}

/** `204`: the API deletes the conversation and its messages. */
export async function deleteConversation(id: string): Promise<void> {
  await apiFetch<void>(`/conversations/${encodeURIComponent(id)}`, { method: "DELETE" });
}
