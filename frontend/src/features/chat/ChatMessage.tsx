import { useState } from "react";
import { Icon } from "../../components/Icon";
import type { Correction, Message, VocabularyItem } from "../../lib/types";

interface ChatMessageProps {
  message: Message;
}

/** Cards of the closing turn (F3 S7, desing.md §6.1.2): corrections and suggested vocabulary. */
function FeedbackCards({
  corrections,
  vocabulary,
}: {
  corrections: Correction[];
  vocabulary: VocabularyItem[];
}) {
  if (corrections.length === 0 && vocabulary.length === 0) return null;

  return (
    <div className="feedback">
      {corrections.length > 0 && (
        <section className="feedback__card" aria-label="Correcciones">
          <p className="feedback__title">Correcciones</p>
          <ul className="feedback__list">
            {corrections.map((correction, index) => (
              <li className="feedback__item" key={`${correction.original}-${index}`}>
                <p className="feedback__change">
                  <del className="feedback__original">
                    <span className="visually-hidden">Original: </span>
                    {correction.original}
                  </del>
                  <span className="visually-hidden">Corrección: </span>
                  <span className="feedback__corrected">{correction.corrected}</span>
                </p>
                {correction.explanation.trim() !== "" && (
                  <p className="feedback__note">{correction.explanation}</p>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

      {vocabulary.length > 0 && (
        <section className="feedback__card" aria-label="Vocabulario">
          <p className="feedback__title">Vocabulario</p>
          <ul className="feedback__list">
            {vocabulary.map((item, index) => (
              <li className="feedback__item" key={`${item.term}-${index}`}>
                <p className="feedback__term">
                  {item.term} <span className="feedback__gloss">{item.translation}</span>
                </p>
                {item.note && <p className="feedback__note">{item.note}</p>}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

export function ChatMessage({ message }: ChatMessageProps) {
  const [showTranslation, setShowTranslation] = useState(false);
  const isTutor = message.author === "tutor";
  const showActions = isTutor && !message.pending && message.content.length > 0;
  const corrections = message.corrections ?? [];
  const vocabulary = message.vocabulary ?? [];

  return (
    <div className={`message message--${message.author}`}>
      {isTutor && (
        <span className="message__avatar" aria-hidden="true">
          <Icon name="chat" size={16} />
        </span>
      )}

      <div className="message__body">
        <div className={`message__bubble${message.pending ? " message__bubble--pending" : ""}`}>
          {message.pending ? (
            // The state stays announced while the first token travels (desing.md §6.1.2).
            <p className="message__pending" aria-live="polite">
              Pensando…
            </p>
          ) : (
            <p className="message__text">{message.content}</p>
          )}
          {showTranslation && !message.pending && (
            <p className="message__translation">
              {message.translation ?? "Traducción no disponible para este mensaje."}
            </p>
          )}
        </div>

        <div className="message__meta">
          {message.timeLabel && <time className="message__time">{message.timeLabel}</time>}
          {message.hasAudio && isTutor && <span className="message__audio-tag">Audio de ejemplo</span>}
          {message.incomplete && <span className="message__incomplete">Respuesta interrumpida</span>}
        </div>

        {!isTutor && <FeedbackCards corrections={corrections} vocabulary={vocabulary} />}

        {showActions && (
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
              title="Pedir una explicación todavía no está implementado"
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
