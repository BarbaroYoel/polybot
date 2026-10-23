import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Notice } from "../../components/Notice";
import { EmptyState, ErrorState, LoadingState } from "../../components/States";
import { sendMessage, streamTurn } from "../../lib/api/chat";
import { errorMessage, isApiError, toApiError } from "../../lib/api/client";
import { getConversation } from "../../lib/api/conversations";
import type {
  ConversationDetail,
  Correction as ApiCorrection,
  Message as ApiMessage,
  VocabularyItem as ApiVocabularyItem,
} from "../../lib/api/types";
import { useActiveLanguage } from "../../lib/language";
import type {
  ChatTurn,
  Correction,
  Message,
  ThreadItem,
  VocabularyItem,
} from "../../lib/types";
import { useAsync } from "../../lib/useAsync";
import { ChatComposer } from "./ChatComposer";
import { ChatThread } from "./ChatThread";
import "./chat.css";

/** Contract limit (docs/api-contract.md §5): one page of messages is the thread of the screen. */
const MESSAGES_LIMIT = 50;

/** How close to the bottom the thread must be for the stream to keep following it. */
const FOLLOW_THRESHOLD = 160;

const timeFormatter = new Intl.DateTimeFormat("es", { hour: "2-digit", minute: "2-digit" });

function formatTime(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "" : timeFormatter.format(date);
}

function toUiCorrection(correction: ApiCorrection): Correction {
  return {
    original: correction.original,
    corrected: correction.corrected,
    explanation: correction.explanation,
  };
}

function toUiVocabulary(item: ApiVocabularyItem): VocabularyItem {
  return {
    term: item.term,
    translation: item.translation,
    note: item.note ?? undefined,
  };
}

/**
 * Contract message (snake_case) → thread message (camelCase UI type). The feedback of the closing
 * turn travels with the user message, so a reload paints the cards again (F3 S7).
 */
function toUiMessage(message: ApiMessage): Message {
  const corrections = (message.feedback?.corrections ?? []).map(toUiCorrection);
  const vocabulary = (message.feedback?.vocabulary ?? []).map(toUiVocabulary);
  return {
    id: message.id,
    author: message.author,
    content: message.content,
    translation: message.translation ?? undefined,
    timeLabel: formatTime(message.created_at),
    corrections: corrections.length > 0 ? corrections : undefined,
    vocabulary: vocabulary.length > 0 ? vocabulary : undefined,
  };
}

/** The tutor bubble before its first token: it says «Pensando…» (desing.md §6.1.2). */
function thinkingTutor(key: string): Message {
  return { id: `pending-${key}`, author: "tutor", content: "", timeLabel: "", pending: true };
}

/** A turn opened from this screen. The user bubble shows up before the POST answers (S9). */
function newTurn(text: string): ChatTurn {
  const key = crypto.randomUUID();
  return {
    key,
    messageId: null,
    status: "sending",
    user: {
      id: `local-${key}`,
      author: "user",
      content: text,
      timeLabel: timeFormatter.format(new Date()),
    },
    tutor: thinkingTutor(key),
    error: null,
  };
}

function isNotFound(error: unknown): boolean {
  return isApiError(error) && error.status === 404;
}

/**
 * Conversation screen (desing.md §6.1.2, ADR-011): thread and composer only. The summary cards
 * live on the home screen.
 *
 * A send runs the turn of the contract (docs/api-contract.md §3): `POST /messages` persists the
 * user message, `GET /stream` streams the tutor reply, and `correction`/`vocabulary` close it with
 * the cards. The screen owns the turn states (`idle → sending → streaming → done | error`), aborts
 * the stream when the user cuts or leaves (S6) and offers «Reintentar» with the same idempotency key
 * when the turn fails (S4, S9).
 *
 * The contract lets `GET /conversations/{id}` take the active language as a guard (S8). The PWA
 * intentionally omits it: desing.md §6.6 wants "cambiar de idioma sin perder la conversación
 * anterior", so the conversation itself decides the context and the screen switches the active
 * language when the link points at another one. The guard stays available to any other consumer
 * that needs the strict answer.
 */
export function ChatPage() {
  const { conversationId } = useParams();
  const {
    languages,
    active,
    status: languageStatus,
    error: languageError,
    reload: reloadLanguages,
    setActiveCode,
  } = useActiveLanguage();
  const [draft, setDraft] = useState("");
  const [turns, setTurns] = useState<ChatTurn[]>([]);

  const scrollRef = useRef<HTMLDivElement>(null);
  const controllerRef = useRef<AbortController | null>(null);
  // Synchronous guard: two Enter presses in the same tick must not open two turns.
  const busyRef = useRef(false);
  const mounted = useRef(true);

  const detail = useAsync<ConversationDetail | null>(async () => {
    if (!conversationId) return null;
    return getConversation(conversationId, { messagesLimit: MESSAGES_LIMIT });
  }, [conversationId]);

  const conversationLanguage = useMemo(
    () => languages.find((language) => language.id === detail.data?.language_id) ?? null,
    [languages, detail.data],
  );

  // desing.md §6.6: opening a conversation of another language moves the context, it does not fail.
  useEffect(() => {
    if (!conversationLanguage || active?.id === conversationLanguage.id) return;
    void setActiveCode(conversationLanguage.code).catch(() => {
      // The thread is already loaded; a failed context switch must not hide it.
    });
  }, [conversationLanguage, active?.id, setActiveCode]);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      // Leaving the screen cuts the turn, which cancels the provider call on the server (S6).
      controllerRef.current?.abort();
    };
  }, []);

  // Turns belong to the conversation on screen: changing it cancels the stream and clears them.
  useEffect(() => {
    controllerRef.current?.abort();
    busyRef.current = false;
    setTurns([]);
  }, [conversationId]);

  const activeTurn = useMemo(
    () => turns.find((turn) => turn.status === "sending" || turn.status === "streaming") ?? null,
    [turns],
  );

  const items = useMemo<ThreadItem[]>(() => {
    const list: ThreadItem[] = (detail.data?.messages.items ?? []).map((message) => ({
      kind: "message",
      message: toUiMessage(message),
    }));
    for (const turn of turns) {
      list.push({ kind: "message", message: turn.user });
      if (turn.tutor) list.push({ kind: "message", message: turn.tutor });
      if (turn.status === "error" && turn.error) {
        list.push({ kind: "turn-error", turnKey: turn.key, message: turn.error });
      }
    }
    return list;
  }, [detail.data, turns]);

  const scrollToBottom = useCallback(() => {
    const element = scrollRef.current;
    if (element) element.scrollTop = element.scrollHeight;
  }, []);

  // Follow the stream while the user is reading the end of the thread; never fight a scroll up.
  useEffect(() => {
    const element = scrollRef.current;
    if (!element) return;
    const distance = element.scrollHeight - element.scrollTop - element.clientHeight;
    if (distance > FOLLOW_THRESHOLD) return;
    element.scrollTop = element.scrollHeight;
  }, [items]);

  /** One turn end to end: POST the message, stream the reply, keep whatever arrived. */
  const runTurn = useCallback(
    async (start: ChatTurn) => {
      if (!conversationId) return;

      const key = start.key;
      const controller = new AbortController();
      controllerRef.current = controller;
      busyRef.current = true;

      let snapshot: ChatTurn = {
        ...start,
        status: start.messageId ? "streaming" : "sending",
        error: null,
        tutor: thinkingTutor(key),
        // A retry replaces the closing feedback of the same message (contract §3): the cards come
        // back only if the new close produces them.
        user: { ...start.user, corrections: undefined, vocabulary: undefined },
      };
      const publish = (patch: Partial<ChatTurn>) => {
        snapshot = { ...snapshot, ...patch };
        if (mounted.current) {
          setTurns((current) => current.map((turn) => (turn.key === key ? snapshot : turn)));
        }
      };
      // Paint the turn as it starts: a retry drops the previous error and the partial tutor text.
      publish({});

      /** The stream declared the turn finished: the text received is complete, not partial. */
      let settled = false;

      try {
        let messageId = start.messageId;
        if (!messageId) {
          const stored = await sendMessage(conversationId, start.user.content, key, {
            signal: controller.signal,
          });
          messageId = stored.id;
          // The stream is open from here on: «Detener» is available before the first token.
          publish({ messageId, user: toUiMessage(stored), status: "streaming" });
        }

        await streamTurn(
          conversationId,
          messageId,
          {
            onToken: ({ message_id, delta }) => {
              const current = snapshot.tutor;
              const content = (current?.content ?? "") + delta;
              // The first token brings the stored tutor id; the placeholder id never reaches the UI.
              const id = current && !current.pending ? current.id : message_id;
              publish({
                status: "streaming",
                tutor: {
                  id,
                  author: "tutor",
                  content,
                  timeLabel: current?.timeLabel ?? "",
                  pending: false,
                },
              });
            },
            onMessageEnd: (message) => {
              // Authoritative message, already persisted as `sent` (contract §3). The close events
              // (`correction`, `vocabulary`) still arrive after it, so the turn waits for the end.
              settled = true;
              publish({ tutor: toUiMessage(message) });
            },
            onCorrections: (_userMessageId, corrections) => {
              publish({
                user: { ...snapshot.user, corrections: corrections.map(toUiCorrection) },
              });
            },
            onVocabulary: (_userMessageId, vocabulary) => {
              publish({
                user: { ...snapshot.user, vocabulary: vocabulary.map(toUiVocabulary) },
              });
            },
          },
          controller.signal,
        );

        publish({ status: "done" });
      } catch (error) {
        const tutor = snapshot.tutor;
        const received = tutor && tutor.content.length > 0 ? tutor : null;
        const partial = received ? { ...received, incomplete: !settled } : null;

        if (controller.signal.aborted) {
          // A cut by the user is not a failure: the partial text stays and no error is shown (S9).
          publish({ status: "done", error: null, tutor: partial });
          return;
        }

        publish({ status: "error", error: errorMessage(toApiError(error)), tutor: partial });
      } finally {
        if (controllerRef.current === controller) {
          controllerRef.current = null;
          busyRef.current = false;
        }
      }
    },
    [conversationId],
  );

  const handleSend = () => {
    const text = draft.trim();
    if (!text || !conversationId || busyRef.current) return;

    setDraft("");
    const turn = newTurn(text);
    busyRef.current = true;
    setTurns((current) => [...current, turn]);
    scrollToBottom();
    void runTurn(turn);
  };

  /** Same turn, same idempotency key: the API resolves it to the message already stored (S4). */
  const handleRetry = (turnKey: string) => {
    if (busyRef.current) return;
    const previous = turns.find((turn) => turn.key === turnKey);
    if (!previous || previous.status !== "error") return;

    busyRef.current = true;
    void runTurn(previous);
  };

  const handleStop = () => {
    controllerRef.current?.abort();
  };

  const handleQuickAction = (label: string) => {
    // A suggestion only loads the composer: the child decides when to send it.
    setDraft(label);
  };

  const recovery = (
    <EmptyState
      title="No encontramos esa conversación"
      description="El enlace apunta a una conversación que no existe en el idioma activo. Puede que pertenezca a otro idioma o que ya se haya eliminado."
      action={
        <Link className="chips__item" to="/">
          Volver al inicio
        </Link>
      }
    />
  );

  const renderBody = () => {
    if (languageStatus === "loading" && !active) {
      return (
        <div className="chat">
          <LoadingState label="Cargando tu idioma…" />
        </div>
      );
    }

    if (detail.status === "loading") {
      return (
        <div className="chat">
          <LoadingState label="Cargando conversación…" />
        </div>
      );
    }

    if (detail.status === "error" && !isNotFound(detail.error)) {
      return (
        <div className="chat">
          <ErrorState
            title="No pudimos cargar esta conversación"
            description={errorMessage(detail.error)}
            action={
              <button type="button" className="chips__item" onClick={detail.reload}>
                Reintentar
              </button>
            }
          />
        </div>
      );
    }

    if (!detail.data) {
      if (languageStatus === "error" && !active) {
        return (
          <div className="chat">
            <ErrorState
              title="No pudimos cargar tus idiomas"
              description={errorMessage(languageError)}
              action={
                <button type="button" className="chips__item" onClick={reloadLanguages}>
                  Reintentar
                </button>
              }
            />
          </div>
        );
      }
      return <div className="chat">{recovery}</div>;
    }

    const hasMoreMessages = Boolean(detail.data.messages.next_cursor);

    return (
      <div className="chat">
        <div className="chat__scroll" ref={scrollRef}>
          {hasMoreMessages && (
            <Notice>
              Se muestran los primeros {MESSAGES_LIMIT} mensajes del hilo. La paginación de
              mensajes todavía no está implementada.
            </Notice>
          )}
          {items.length === 0 ? (
            <EmptyState
              title="Esta conversación todavía no tiene mensajes"
              description="Está recién creada. Escribe el primer mensaje y el tutor te responde."
            />
          ) : (
            <ChatThread items={items} onQuickAction={handleQuickAction} onRetry={handleRetry} />
          )}
        </div>

        <div className="chat__composer-wrap">
          <ChatComposer
            value={draft}
            onChange={setDraft}
            onSend={handleSend}
            onStop={handleStop}
            busy={activeTurn !== null}
            streaming={activeTurn?.status === "streaming"}
          />
        </div>
      </div>
    );
  };

  return renderBody();
}
