import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Icon } from "../../components/Icon";
import { Notice } from "../../components/Notice";
import { EmptyState, ErrorState, LoadingState } from "../../components/States";
import { SummaryCard } from "../../components/SummaryCard";
import { errorMessage } from "../../lib/api/client";
import { createConversation, listConversations } from "../../lib/api/conversations";
import type { Conversation, ConversationPage } from "../../lib/api/types";
import { EXAMPLE_DATA } from "../../lib/fixtures";
import { useActiveLanguage } from "../../lib/language";
import { useAsync } from "../../lib/useAsync";
import "./home.css";

const EXAMPLE_NOTICE =
  "Datos de ejemplo solo en las secciones Lecciones, Planes de estudio, Traducción y Progreso. Las conversaciones y los idiomas ya se leen del backend.";

/** Upper bound of the contract (docs/api-contract.md §5): the history asks for the maximum page. */
const HISTORY_LIMIT = 50;

const EMPTY_PAGE: ConversationPage = { items: [], next_cursor: null };

const activityFormatter = new Intl.DateTimeFormat("es", {
  day: "numeric",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
});

/** `last_message_at` is ISO 8601 UTC; the list shows it in the reader's local time. */
function formatActivity(value: string | null): string {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "" : activityFormatter.format(date);
}

function messagesLabel(count: number): string {
  return count === 1 ? "1 mensaje" : `${count} mensajes`;
}

function conversationMeta(conversation: Conversation): string {
  const activity = formatActivity(conversation.last_message_at);
  return activity
    ? `${messagesLabel(conversation.message_count)} · último ${activity}`
    : `${messagesLabel(conversation.message_count)} · sin mensajes todavía`;
}

/**
 * Home screen (desing.md §6.1, ADR-011): summary cards and the real conversation history of the
 * active language. A conversation lives at `/chat/:id`.
 */
export function HomePage() {
  const {
    active,
    status: languageStatus,
    error: languageError,
    reload: reloadLanguages,
  } = useActiveLanguage();
  const navigate = useNavigate();
  const history = useAsync(
    () => (active ? listConversations(active.id, { limit: HISTORY_LIMIT }) : Promise.resolve(EMPTY_PAGE)),
    [active?.id],
  );
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const headingId = "home-conversations-title";

  const handleNewConversation = async () => {
    if (!active || creating) return;
    setCreating(true);
    setCreateError(null);
    try {
      const conversation = await createConversation({ languageId: active.id });
      navigate(`/chat/${conversation.id}`);
    } catch (error: unknown) {
      setCreateError(errorMessage(error));
    } finally {
      setCreating(false);
    }
  };

  const renderHistory = () => {
    if (languageStatus === "loading" && !active) {
      return <LoadingState label="Cargando tu idioma…" />;
    }

    if (languageStatus === "error" && !active) {
      return (
        <ErrorState
          title="No pudimos cargar tus idiomas"
          description={errorMessage(languageError)}
          action={
            <button type="button" className="home__action" onClick={reloadLanguages}>
              Reintentar
            </button>
          }
        />
      );
    }

    if (!active) {
      return (
        <EmptyState
          title="Todavía no hay un idioma activo"
          description="Elige un idioma en Mis idiomas para ver su historial de conversaciones. Cada idioma conserva el suyo."
          action={
            <Link className="home__action" to="/languages">
              Ir a Mis idiomas
            </Link>
          }
        />
      );
    }

    if (history.status === "loading") {
      return <LoadingState label={`Cargando conversaciones en ${active.name}…`} />;
    }

    if (history.status === "error") {
      return (
        <ErrorState
          title="No pudimos cargar tus conversaciones"
          description={errorMessage(history.error)}
          action={
            <button type="button" className="home__action" onClick={history.reload}>
              Reintentar
            </button>
          }
        />
      );
    }

    const conversations = history.data?.items ?? [];

    if (conversations.length === 0) {
      return (
        <EmptyState
          title={`Sin conversaciones en ${active.name} todavía`}
          description="Empieza una conversación nueva con el botón de arriba. Tu historial de otros idiomas queda intacto."
        />
      );
    }

    return (
      <ul className="home__list">
        {conversations.map((conversation) => (
          <li key={conversation.id}>
            <Link className="home__conversation" to={`/chat/${conversation.id}`}>
              <span className="home__conversation-icon" aria-hidden="true">
                <Icon name="chat" size={18} />
              </span>
              <span className="home__conversation-main">
                <span className="home__conversation-title">{conversation.title}</span>
                <span className="home__conversation-meta">{conversationMeta(conversation)}</span>
              </span>
              <span className="home__conversation-go" aria-hidden="true">
                <Icon name="arrowRight" size={18} />
              </span>
            </Link>
          </li>
        ))}
      </ul>
    );
  };

  return (
    <div className="home">
      <div className="home__summaries">
        <SummaryCard
          icon="book"
          title="Lección de hoy"
          meta="Vocabulario en situaciones cotidianas"
          progress={{ current: 3, total: 5 }}
          actionLabel="Continuar"
          actionTitle="Las lecciones llegan en F5"
        />
        <SummaryCard
          icon="target"
          title="Meta semanal"
          meta="4 de 7 conversaciones"
          dots={{ current: 4, total: 7 }}
        />
        <SummaryCard
          icon="calendar"
          title="Próxima práctica"
          meta="Hoy, 17:00 · Conversación: en un café"
          actionLabel="Abrir"
          actionTitle="La planificación llega en F5"
        />
      </div>

      {EXAMPLE_DATA && <Notice>{EXAMPLE_NOTICE}</Notice>}

      <section className="home__history" aria-labelledby={headingId}>
        <div className="home__history-head">
          <h2 className="home__history-title" id={headingId}>
            {active ? `Conversaciones en ${active.name}` : "Conversaciones"}
          </h2>
          <button
            type="button"
            className="home__new"
            onClick={() => void handleNewConversation()}
            disabled={!active || creating}
            title={
              active
                ? "Empezar una conversación nueva en este idioma"
                : "Activa un idioma para empezar una conversación"
            }
          >
            {creating ? "Creando…" : "Nueva conversación"}
          </button>
        </div>

        {createError && <Notice live>{createError}</Notice>}

        {renderHistory()}

        {history.data?.next_cursor && (
          <Notice>
            Se muestran las {HISTORY_LIMIT} conversaciones más recientes. La paginación del
            historial todavía no está implementada.
          </Notice>
        )}
      </section>
    </div>
  );
}
