import { Link } from "react-router-dom";
import { Icon } from "../../components/Icon";
import { Notice } from "../../components/Notice";
import { EmptyState } from "../../components/States";
import { SummaryCard } from "../../components/SummaryCard";
import { EXAMPLE_DATA, listConversations } from "../../lib/fixtures";
import { useActiveLanguage } from "../../lib/language";
import "./home.css";

const EXAMPLE_NOTICE =
  "Datos de ejemplo — todavía no hay backend. Los controles que aún no tienen función están deshabilitados y explican por qué.";

/**
 * Home screen (desing.md §6.1, ADR-011): summary cards and the conversations of
 * the active language. A conversation lives at `/chat/:id`.
 */
export function HomePage() {
  const { active } = useActiveLanguage();
  const conversations = listConversations(active.code);
  const headingId = "home-conversations-title";

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
            Conversaciones en {active.name}
          </h2>
          <button
            type="button"
            className="chips__item home__new"
            disabled
            title="Crear conversaciones llega con el backend (F2)"
          >
            Nueva conversación
          </button>
        </div>

        {conversations.length === 0 ? (
          <EmptyState
            title={`Sin conversaciones en ${active.name} todavía`}
            description="Cuando exista el backend vas a poder empezar una conversación nueva en este idioma. Tu historial de otros idiomas queda intacto."
          />
        ) : (
          <ul className="home__list">
            {conversations.map((conversation) => {
              const lastMessage = conversation.messages[conversation.messages.length - 1];
              return (
                <li key={conversation.id}>
                  <Link className="home__conversation" to={`/chat/${conversation.id}`}>
                    <span className="home__conversation-icon" aria-hidden="true">
                      <Icon name="chat" size={18} />
                    </span>
                    <span className="home__conversation-main">
                      <span className="home__conversation-title">{conversation.title}</span>
                      <span className="home__conversation-meta">
                        {conversation.messages.length} mensajes
                        {lastMessage ? ` · último ${lastMessage.timeLabel}` : ""}
                      </span>
                    </span>
                    <span className="home__conversation-go" aria-hidden="true">
                      <Icon name="arrowRight" size={18} />
                    </span>
                  </Link>
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </div>
  );
}
