import { useMemo, useState } from "react";
import { EmptyState } from "../../components/States";
import { SummaryCard } from "../../components/SummaryCard";
import { EXAMPLE_DATA, findConversation } from "../../lib/fixtures";
import { useActiveLanguage } from "../../lib/language";
import type { Message } from "../../lib/types";
import { ChatComposer } from "./ChatComposer";
import { ChatThread } from "./ChatThread";
import "./chat.css";

function timeLabel(): string {
  return new Intl.DateTimeFormat("es", { hour: "2-digit", minute: "2-digit" }).format(new Date());
}

export function ChatPage() {
  const { active } = useActiveLanguage();
  const conversation = findConversation(active.code);
  const [draft, setDraft] = useState("");
  const [sent, setSent] = useState<Record<string, Message[]>>({});
  const [notice, setNotice] = useState<string | null>(null);

  const messages = useMemo<Message[]>(
    () => [...(conversation?.messages ?? []), ...(sent[active.code] ?? [])],
    [conversation, sent, active.code],
  );

  const handleSend = () => {
    const text = draft.trim();
    if (!text) return;
    const message: Message = {
      id: `local-${Date.now()}`,
      author: "user",
      content: text,
      timeLabel: timeLabel(),
    };
    setSent((current) => ({ ...current, [active.code]: [...(current[active.code] ?? []), message] }));
    setDraft("");
    setNotice("Prototipo sin backend: el mensaje queda solo en esta sesión y el tutor no responde todavía.");
  };

  const handleQuickAction = (label: string) => {
    setDraft(label);
    setNotice(`Sugerencia cargada en el compositor: «${label}». Las acciones guiadas llegan en F3.`);
  };

  return (
    <div className="chat">
      <div className="chat__summaries">
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

      {EXAMPLE_DATA && (
        <p className="chat__notice">
          Datos de ejemplo — todavía no hay backend. Los controles que aún no tienen función están
          deshabilitados y explican por qué.
        </p>
      )}

      <div className="chat__scroll">
        {messages.length === 0 ? (
          <EmptyState
            title={`Sin conversaciones en ${active.name} todavía`}
            description="Cuando exista el backend vas a poder empezar una conversación nueva en este idioma. Tu historial de otros idiomas queda intacto."
            action={
              <button
                type="button"
                className="chips__item"
                disabled
                title="Crear conversaciones llega con el backend (F2)"
              >
                Nueva conversación
              </button>
            }
          />
        ) : (
          <ChatThread messages={messages} onQuickAction={handleQuickAction} />
        )}
      </div>

      <div className="chat__composer-wrap">
        {notice && (
          <p className="chat__notice" role="status" aria-live="polite">
            {notice}
          </p>
        )}
        <ChatComposer value={draft} onChange={setDraft} onSend={handleSend} />
      </div>
    </div>
  );
}
