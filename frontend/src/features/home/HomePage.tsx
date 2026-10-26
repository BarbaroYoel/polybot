import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Icon } from "../../components/Icon";
import { Notice } from "../../components/Notice";
import { EmptyState, ErrorState, LoadingState } from "../../components/States";
import { SummaryCard } from "../../components/SummaryCard";
import { errorMessage } from "../../lib/api/client";
import { createConversation, listConversations } from "../../lib/api/conversations";
import { getLessonCatalog } from "../../lib/api/lessons";
import { getPlan } from "../../lib/api/plans";
import type {
  Conversation,
  ConversationPage,
  LanguagePlan,
  LessonCatalog,
} from "../../lib/api/types";
import { useActiveLanguage } from "../../lib/language";
import { useAsync } from "../../lib/useAsync";
import "./home.css";

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

/** Lesson totals of the catalog, derived from the states the API returned (F5 S5). */
function lessonTotals(catalog: LessonCatalog): { total: number; completed: number } {
  let total = 0;
  let completed = 0;
  for (const unit of catalog.units) {
    for (const lesson of unit.lessons) {
      total += 1;
      if (lesson.status === "completed") completed += 1;
    }
  }
  return { total, completed };
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
  // F5 entries: the next lesson and the next plan session are real, not sample values.
  const catalog = useAsync<LessonCatalog | null>(
    () => (active ? getLessonCatalog(active.id) : Promise.resolve(null)),
    [active?.id],
  );
  const plan = useAsync<LanguagePlan | null>(
    () => (active ? getPlan(active.id) : Promise.resolve(null)),
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

  const renderLessonCard = () => {
    if (!active) {
      return (
        <SummaryCard
          icon="book"
          title="Lección de hoy"
          meta="Activa un idioma para ver su catálogo de lecciones."
        />
      );
    }

    if (catalog.status === "loading") {
      return (
        <SummaryCard
          icon="book"
          title="Lección de hoy"
          meta={`Cargando el catálogo en ${active.name}…`}
        />
      );
    }

    if (catalog.status === "error") {
      return (
        <SummaryCard
          icon="book"
          title="Lección de hoy"
          meta="No pudimos cargar la lección de hoy."
          actionLabel="Reintentar"
          onAction={catalog.reload}
        />
      );
    }

    const data = catalog.data;
    if (!data) {
      return (
        <SummaryCard
          icon="book"
          title="Lección de hoy"
          meta="Este idioma todavía no tiene lecciones."
          actionLabel="Ver lecciones"
          onAction={() => navigate("/lessons")}
        />
      );
    }

    const totals = lessonTotals(data);
    const next = data.next_lesson;

    if (!next) {
      return (
        <SummaryCard
          icon="book"
          title="Lección de hoy"
          meta={
            totals.total === 0
              ? "Este idioma todavía no tiene lecciones."
              : "Completaste todas las lecciones de este catálogo."
          }
          actionLabel="Ver lecciones"
          onAction={() => navigate("/lessons")}
        />
      );
    }

    return (
      <SummaryCard
        icon="book"
        title="Lección de hoy"
        meta={`${next.title} · ${next.difficulty} · ${next.estimated_minutes} min`}
        progress={totals.total > 0 ? { current: totals.completed, total: totals.total } : undefined}
        actionLabel={next.status === "in_progress" ? "Retomar" : "Continuar"}
        onAction={() => navigate(`/lessons/${next.id}`)}
      />
    );
  };

  const renderGoalCard = () => {
    if (!active) {
      return (
        <SummaryCard
          icon="target"
          title="Meta semanal"
          meta="Activa un idioma para ver su meta."
        />
      );
    }

    return (
      <SummaryCard
        icon="target"
        title="Meta semanal"
        meta={`${active.weekly_goal.conversations} conversaciones y ${active.weekly_goal.minutes} min por semana. El avance llega con Progreso (F6).`}
      />
    );
  };

  const renderPlanCard = () => {
    if (!active) {
      return (
        <SummaryCard
          icon="calendar"
          title="Próxima sesión"
          meta="Activa un idioma para ver su plan de estudio."
        />
      );
    }

    if (plan.status === "loading") {
      return (
        <SummaryCard
          icon="calendar"
          title="Próxima sesión"
          meta={`Cargando el plan en ${active.name}…`}
        />
      );
    }

    if (plan.status === "error") {
      return (
        <SummaryCard
          icon="calendar"
          title="Próxima sesión"
          meta="No pudimos cargar el plan de estudio."
          actionLabel="Reintentar"
          onAction={plan.reload}
        />
      );
    }

    const value = plan.data?.plan ?? null;
    if (!value) {
      return (
        <SummaryCard
          icon="calendar"
          title="Próxima sesión"
          meta="Todavía no hay un plan de estudio para este idioma."
          actionLabel="Crear plan"
          onAction={() => navigate("/plans")}
        />
      );
    }

    const next = value.next_session;
    if (value.sessions.length === 0) {
      return (
        <SummaryCard
          icon="calendar"
          title="Próxima sesión"
          meta="El plan todavía no tiene sesiones: el catálogo del idioma no tiene lecciones."
          actionLabel="Ver plan"
          onAction={() => navigate("/plans")}
        />
      );
    }

    if (!next) {
      return (
        <SummaryCard
          icon="calendar"
          title="Próxima sesión"
          meta="Todas las sesiones del plan están completadas."
          actionLabel="Ver plan"
          onAction={() => navigate("/plans")}
        />
      );
    }

    return (
      <SummaryCard
        icon="calendar"
        title="Próxima sesión"
        meta={`Semana ${next.week} · ${next.lesson_title}`}
        actionLabel="Abrir"
        onAction={() => navigate(`/lessons/${next.lesson_id}`)}
      />
    );
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
        {renderLessonCard()}
        {renderGoalCard()}
        {renderPlanCard()}
      </div>

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
