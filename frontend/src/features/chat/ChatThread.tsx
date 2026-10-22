import { QUICK_ACTIONS } from "../../lib/fixtures";
import type { Message } from "../../lib/types";
import { ChatMessage } from "./ChatMessage";

interface ChatThreadProps {
  messages: Message[];
  onQuickAction: (label: string) => void;
}

export function ChatThread({ messages, onQuickAction }: ChatThreadProps) {
  const lastTutorIndex = messages.reduce(
    (last, message, index) => (message.author === "tutor" ? index : last),
    -1,
  );

  return (
    <ol className="thread" aria-label="Conversación">
      {messages.map((message, index) => (
        <li key={message.id} className="thread__item">
          <ChatMessage message={message} />

          {index === lastTutorIndex && (
            <div className="chips" aria-label="Sugerencias rápidas">
              {QUICK_ACTIONS.map((action) => (
                <button
                  key={action}
                  type="button"
                  className="chips__item"
                  onClick={() => onQuickAction(action)}
                >
                  {action}
                </button>
              ))}
            </div>
          )}
        </li>
      ))}
    </ol>
  );
}
