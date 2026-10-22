import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Notice } from "../../components/Notice";
import { EmptyState } from "../../components/States";
import { EXAMPLE_DATA, findConversationById } from "../../lib/fixtures";
import { useActiveLanguage } from "../../lib/language";
import type { Message } from "../../lib/types";
import { ChatComposer } from "./ChatComposer";
import { ChatThread } from "./ChatThread";
import "./chat.css";

const EXAMPLE_NOTICE =
  "Datos de ejemplo — todavía no hay backend. Los controles que aún no tienen función están deshabilitados y explican por qué.";

function timeLabel(): string {
  return new Intl.DateTimeFormat("es", { hour: "2-digit", minute: "2-digit" }).format(new Date());
}

/**
 * Conversation screen (desing.md §6.1, ADR-011): thread and composer only.
 * The summary cards live on the home screen.
 */
export function ChatPage() {
  const { conversationId } = useParams();
  const { active, setActiveCode } = useActiveLanguage();
  const conversation = findConversationById(conversationId);
  const [draft, setDraft] = useState("");
  const [sent, setSent] = useState<Record<string, Message[]>>({});
  const [notice, setNotice] = useState<string | null>(null);

  // Opening a conversation in another language switches the active context (desing.md §8).
  useEffect(() => {
    if (conversation && conversation.languageCode !== active.code) {
      setActiveCode(conversation.languageCode);
    }
  }, [conversation, active.code, setActiveCode]);

  const sentHere = conversationId ? sent[conversationId] ?? [] : [];

  const messages = useMemo<Message[]>(
    () => [...(conversation?.messages ?? []), ...sentHere],
    [conversation, sentHere],
  );

  const handleSend = () => {
    const text = draft.trim();
    if (!text || !conversationId) return;
    const message: Message = {
      id: `local-${Date.now()}`,
      author: "user",
      content: text,
      timeLabel: timeLabel(),
    };
    setSent((current) => ({
      ...current,
      [conversationId]: [...(current[conversationId] ?? []), message],
    }));
    setDraft("");
    setNotice("Prototipo sin backend: el mensaje queda solo en esta sesión y el tutor no responde todavía.");
  };

  const handleQuickAction = (label: string) => {
    setDraft(label);
    setNotice(`Sugerencia cargada en el compositor: «${label}». Las acciones guiadas llegan en F3.`);
  };

  if (!conversation) {
    return (
      <div className="chat">
        <EmptyState
          title="No encontramos esa conversación"
          description="El enlace apunta a una conversación que no existe entre los datos de ejemplo. Puede que pertenezca a otro idioma o que el enlace esté incompleto."
          action={
            <Link className="chips__item" to="/">
              Volver al inicio
            </Link>
          }
        />
      </div>
    );
  }

  const footerNotice = notice ?? (EXAMPLE_DATA ? EXAMPLE_NOTICE : null);

  return (
    <div className="chat">
      <div className="chat__scroll">
        <ChatThread messages={messages} onQuickAction={handleQuickAction} />
      </div>

      <div className="chat__composer-wrap">
        {footerNotice && <Notice live={Boolean(notice)}>{footerNotice}</Notice>}
        <ChatComposer value={draft} onChange={setDraft} onSend={handleSend} />
      </div>
    </div>
  );
}
