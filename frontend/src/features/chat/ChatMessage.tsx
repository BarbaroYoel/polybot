import { useState } from "react";
import { Icon } from "../../components/Icon";
import type { Message } from "../../lib/types";

interface ChatMessageProps {
  message: Message;
}

export function ChatMessage({ message }: ChatMessageProps) {
  const [showTranslation, setShowTranslation] = useState(false);
  const isTutor = message.author === "tutor";

  return (
    <div className={`message message--${message.author}`}>
      {isTutor && (
        <span className="message__avatar" aria-hidden="true">
          <Icon name="chat" size={16} />
        </span>
      )}

      <div className="message__body">
        <div className="message__bubble">
          <p className="message__text">{message.content}</p>
          {showTranslation && (
            <p className="message__translation">
              {message.translation ?? "Traducción no disponible para este mensaje."}
            </p>
          )}
        </div>

        <div className="message__meta">
          <time className="message__time">{message.timeLabel}</time>
          {message.hasAudio && isTutor && <span className="message__audio-tag">Audio de ejemplo</span>}
        </div>

        {isTutor && (
          <div className="message__actions">
            <button
              type="button"
              className="message__action"
              disabled
              title="Escuchar en voz alta llega en F4 con Piper"
            >
              <Icon name="volume" size={15} />
              Escuchar
            </button>
            <button
              type="button"
              className="message__action"
              onClick={() => setShowTranslation((value) => !value)}
              aria-pressed={showTranslation}
            >
              <Icon name="translate" size={15} />
              {showTranslation ? "Ocultar traducción" : "Traducir"}
            </button>
            <button
              type="button"
              className="message__action"
              disabled
              title="Requiere el backend del tutor (F3)"
            >
              No entiendo
            </button>
            <button
              type="button"
              className="message__action"
              disabled
              title="La reproducción lenta llega con el audio (F4)"
            >
              Más lento
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
