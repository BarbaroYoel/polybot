import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Notice } from "../../components/Notice";
import { EmptyState, ErrorState, LoadingState } from "../../components/States";
import { errorMessage, isApiError } from "../../lib/api/client";
import { getConversation } from "../../lib/api/conversations";
import type { ConversationDetail, Message as ApiMessage } from "../../lib/api/types";
import { useActiveLanguage } from "../../lib/language";
import type { Message } from "../../lib/types";
import { useAsync } from "../../lib/useAsync";
import { ChatComposer } from "./ChatComposer";
import { ChatThread } from "./ChatThread";
import "./chat.css";

/**
 * The tutor has no LLM yet (F3): sending stays local and the notice says exactly that, instead of
 * pretending the message reached a backend.
 */
const PROTOTYPE_NOTICE =
  "El tutor todavía no responde: el envío de mensajes llega en F3. Lo que escribas ahora queda solo en esta sesión.";

/** Contract limit (docs/api-contract.md §5): one page of messages is enough for the thread in F2. */
const MESSAGES_LIMIT = 50;

const NO_MESSAGES: Message[] = [];

const timeFormatter = new Intl.DateTimeFormat("es", { hour: "2-digit", minute: "2-digit" });

function formatTime(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "" : timeFormatter.format(date);
}

/** Contract message (snake_case) → thread message (camelCase UI type). */
function toUiMessage(message: ApiMessage): Message {
  return {
    id: message.id,
    author: message.author,
    content: message.content,
    translation: message.translation ?? undefined,
    timeLabel: formatTime(message.created_at),
  };
}

function isNotFound(error: unknown): boolean {
  return isApiError(error) && error.status === 404;
}

/**
 * Conversation screen (desing.md §6.1.2, ADR-011): thread and composer only. The summary cards
 * live on the home screen.
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
  const [sent, setSent] = useState<Record<string, Message[]>>({});
  const [notice, setNotice] = useState<string | null>(null);

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

  const sentHere = (conversationId ? sent[conversationId] : undefined) ?? NO_MESSAGES;

  const messages = useMemo<Message[]>(
    () => [...(detail.data?.messages.items ?? []).map(toUiMessage), ...sentHere],
    [detail.data, sentHere],
  );

  const handleSend = () => {
    const text = draft.trim();
    if (!text || !conversationId) return;
    const message: Message = {
      id: `local-${Date.now()}`,
      author: "user",
      content: text,
      timeLabel: timeFormatter.format(new Date()),
    };
    setSent((current) => ({
      ...current,
      [conversationId]: [...(current[conversationId] ?? []), message],
    }));
    setDraft("");
    setNotice(PROTOTYPE_NOTICE);
  };

  const handleQuickAction = (label: string) => {
    setDraft(label);
    setNotice(`Sugerencia cargada en el compositor: «${label}». Las acciones guiadas llegan en F3.`);
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
        <div className="chat__scroll">
          {hasMoreMessages && (
            <Notice>
              Se muestran los primeros {MESSAGES_LIMIT} mensajes del hilo. La paginación de
              mensajes todavía no está implementada.
            </Notice>
          )}
          {messages.length === 0 ? (
            <EmptyState
              title="Esta conversación todavía no tiene mensajes"
              description="Está recién creada. El tutor empieza a responder cuando el envío de mensajes llegue en F3."
            />
          ) : (
            <ChatThread messages={messages} onQuickAction={handleQuickAction} />
          )}
        </div>

        <div className="chat__composer-wrap">
          <Notice live={Boolean(notice)}>{notice ?? PROTOTYPE_NOTICE}</Notice>
          <ChatComposer value={draft} onChange={setDraft} onSend={handleSend} />
        </div>
      </div>
    );
  };

  return renderBody();
}
