import { useRef, useState } from "react";
import { Icon } from "../../components/Icon";
import type { Correction, Message, VocabularyItem } from "../../lib/types";
import { useSpeech } from "./useSpeech";

interface ChatMessageProps {
  message: Message;
  /** The conversation's language: the voice of «Escuchar» comes from it (F4 S3). */
  languageCode?: string;
  /** Translates and stores the whole message; resolves the stored translation (S2). */
  onTranslateMessage: (messageId: string) => Promise<string>;
  /** Translates a selected fragment; nothing is stored (S1, S2). */
  onTranslateFragment: (text: string) => Promise<string>;
}

/**
 * The text selected inside `node`, trimmed, or `null` (S1).
 *
 * The selection has to start *and* end inside this bubble: a selection that crosses two messages
 * would be translated as one text, which is neither what the button promises nor what the user
 * picked.
 */
function selectionWithin(node: HTMLElement | null): string | null {
  if (!node) return null;
  const selection = window.getSelection();
  if (!selection || selection.isCollapsed || selection.rangeCount === 0) return null;
  const range = selection.getRangeAt(0);
  if (!node.contains(range.startContainer) || !node.contains(range.endContainer)) return null;
  const text = range.toString().trim();
  return text.length > 0 ? text : null;
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

export function ChatMessage({
  message,
  languageCode,
  onTranslateMessage,
  onTranslateFragment,
}: ChatMessageProps) {
  const bubbleRef = useRef<HTMLDivElement>(null);
  // The last selection made inside this bubble. A click on the button can collapse the selection
  // before the handler runs, so the bubble remembers the last one it saw.
  const selectedRef = useRef<string | null>(null);
  const [showTranslation, setShowTranslation] = useState(false);
  // The stored translation of the whole message, or the fragment's while it is on screen (S2).
  const [translation, setTranslation] = useState<string | null>(message.translation ?? null);
  // Which fragment the panel is showing; `null` means the whole message.
  const [fragment, setFragment] = useState<string | null>(null);
  const [translationStatus, setTranslationStatus] = useState<"idle" | "loading" | "error">(
    "idle",
  );
  const isTutor = message.author === "tutor";
  const showActions = isTutor && !message.pending && message.content.length > 0;
  const corrections = message.corrections ?? [];
  const vocabulary = message.vocabulary ?? [];
  const speech = useSpeech({ text: message.content, languageCode });

  async function translateFragment(text: string): Promise<void> {
    setShowTranslation(true);
    setTranslationStatus("loading");
    try {
      setTranslation(await onTranslateFragment(text));
      setFragment(text);
      setTranslationStatus("idle");
    } catch {
      setTranslationStatus("error");
    }
  }

  async function translateWholeMessage(): Promise<void> {
    setShowTranslation(true);
    setTranslationStatus("loading");
    try {
      setTranslation(await onTranslateMessage(message.id));
      setFragment(null);
      setTranslationStatus("idle");
    } catch {
      setTranslationStatus("error");
    }
  }

  /** Remember the selection of this bubble while it is being made (mouse or keyboard). */
  function rememberSelection(): void {
    const selected = selectionWithin(bubbleRef.current);
    if (selected !== null) selectedRef.current = selected;
  }

  /**
   * One button, three outcomes (S1, S6): a selection of this bubble always wins and translates only
   * the fragment; without a selection it hides what is open, shows a stored translation, or
   * translates the whole message.
   */
  function handleTranslate(): void {
    if (translationStatus === "loading") return;

    const selected = selectionWithin(bubbleRef.current) ?? selectedRef.current;
    if (selected !== null) {
      selectedRef.current = null;
      void translateFragment(selected);
      return;
    }
    if (showTranslation) {
      setShowTranslation(false);
      return;
    }
    // A stored translation is not asked for again; a fragment's is not the whole message's.
    if (translation !== null && fragment === null) {
      setShowTranslation(true);
      return;
    }
    void translateWholeMessage();
  }

  const translationLabel = showTranslation ? "Ocultar traducción" : "Traducir";

  return (
    <div className={`message message--${message.author}`}>
      {isTutor && (
        <span className="message__avatar" aria-hidden="true">
          <Icon name="chat" size={16} />
        </span>
      )}

      <div className="message__body">
        <div
          className={`message__bubble${message.pending ? " message__bubble--pending" : ""}`}
          ref={bubbleRef}
          onMouseUp={rememberSelection}
          onKeyUp={rememberSelection}
        >
          {message.pending ? (
            // The state stays announced while the first token travels (desing.md §6.1.2).
            <p className="message__pending" aria-live="polite">
              Pensando…
            </p>
          ) : (
            <p className="message__text">{message.content}</p>
          )}
          {showTranslation && !message.pending && (
            <p className="message__translation" aria-live="polite">
              {translationStatus === "loading" && "Traduciendo…"}
              {translationStatus === "error" && (
                <span className="message__translation-error">
                  No pudimos traducir.{" "}
                  <button
                    type="button"
                    className="message__retry"
                    onClick={() => {
                      if (fragment !== null) void translateFragment(fragment);
                      else void translateWholeMessage();
                    }}
                  >
                    Reintentar
                  </button>
                </span>
              )}
              {translationStatus === "idle" && translation !== null && (
                <>
                  {fragment !== null && (
                    <span className="message__translation-source">«{fragment}»{" "}</span>
                  )}
                  {translation}
                </>
              )}
            </p>
          )}
        </div>

        <div className="message__meta">
          {message.timeLabel && <time className="message__time">{message.timeLabel}</time>}
          {message.hasAudio && isTutor && <span className="message__audio-tag">Audio de ejemplo</span>}
          {message.incomplete && <span className="message__incomplete">Respuesta interrumpida</span>}
          {speech.status === "loading" && (
            <span className="message__speech" aria-live="polite">
              Preparando el audio…
            </span>
          )}
          {speech.status === "playing" && (
            <span className="message__speech" aria-live="polite">
              Reproduciendo…
            </span>
          )}
        </div>

        {speech.error && (
          <p className="message__speech-error" role="alert">
            {speech.error}{" "}
            <button
              type="button"
              className="message__retry"
              onClick={() => void speech.play(1)}
            >
              Reintentar
            </button>
          </p>
        )}

        {!isTutor && <FeedbackCards corrections={corrections} vocabulary={vocabulary} />}

        {showActions && (
          <div className="message__actions">
            <button
              type="button"
              className="message__action"
              onClick={() => void speech.play(1)}
              disabled={speech.status === "loading"}
              aria-pressed={speech.status === "playing"}
              title={speech.status === "playing" ? "Detener la reproducción" : "Escuchar el mensaje"}
            >
              <Icon name="volume" size={15} />
              {speech.status === "playing" ? "Detener" : "Escuchar"}
            </button>
            <button
              type="button"
              className="message__action"
              onClick={handleTranslate}
              // Keep the text selection alive while the click lands (S1).
              onMouseDown={(event) => event.preventDefault()}
              aria-pressed={showTranslation}
              disabled={translationStatus === "loading"}
            >
              <Icon name="translate" size={15} />
              {translationLabel}
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
              onClick={() => void speech.play(0.75)}
              disabled={speech.status === "loading"}
              title="Escuchar el mensaje más despacio"
            >
              Más lento
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
