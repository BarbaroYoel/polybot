import { QUICK_ACTIONS } from "../../lib/fixtures";
import type { DrillResult, ThreadItem } from "../../lib/types";
import { ChatMessage } from "./ChatMessage";

interface ChatThreadProps {
  items: ThreadItem[];
  onQuickAction: (label: string) => void;
  /** Retries a failed turn with the same idempotency key (F3 S9). */
  onRetry: (turnKey: string) => void;
  onTranslateMessage: (messageId: string) => Promise<string>;
  onTranslateFragment: (text: string) => Promise<string>;
  /** Grades a drill of one message (ADR-020). */
  onAnswerBlock: (messageId: string, blockId: string, answer: string) => Promise<DrillResult>;
  /** The conversation's language, so «Escuchar» uses the right voice (F4 S3). */
  languageCode?: string;
}

export function ChatThread({
  items,
  onQuickAction,
  onRetry,
  onTranslateMessage,
  onTranslateFragment,
  onAnswerBlock,
  languageCode,
}: ChatThreadProps) {
  const last = items.length > 0 ? items[items.length - 1] : null;
  const lastMessage = last?.kind === "message" ? last.message : null;
  // Suggestions belong to a finished tutor answer (desing.md §6.1.2): not while it is thinking,
  // not on text a failed or cut stream left behind.
  const showQuickActions =
    lastMessage?.author === "tutor" && !lastMessage.pending && !lastMessage.incomplete;

  return (
    <ol className="thread" aria-label="Conversación">
      {items.map((item, index) => {
        if (item.kind === "turn-error") {
          return (
            <li className="thread__item" key={`turn-error-${item.turnKey}`}>
              <div className="thread__error" role="alert">
                <p className="thread__error-text">{item.message}</p>
                <button
                  type="button"
                  className="chips__item"
                  onClick={() => onRetry(item.turnKey)}
                >
                  Reintentar
                </button>
              </div>
            </li>
          );
        }

        return (
          <li className="thread__item" key={item.message.id}>
            <ChatMessage
              message={item.message}
              languageCode={languageCode}
              onTranslateMessage={onTranslateMessage}
              onTranslateFragment={onTranslateFragment}
              onAnswerBlock={(blockId, answer) =>
                onAnswerBlock(item.message.id, blockId, answer)
              }
            />

            {index === items.length - 1 && showQuickActions && (
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
        );
      })}
    </ol>
  );
}
