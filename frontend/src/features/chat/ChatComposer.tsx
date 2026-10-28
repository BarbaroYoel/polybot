import { useCallback, useRef } from "react";
import type { KeyboardEvent } from "react";
import { Icon } from "../../components/Icon";
import { useVoiceInput } from "./useVoiceInput";

interface ChatComposerProps {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  /** Cuts the running turn; the partial reply stays visible (F3 S6, S9). */
  onStop: () => void;
  /** A turn is in flight (`sending` or `streaming`): the send action waits for it. */
  busy: boolean;
  /** The SSE stream is open: only then does «Detener» make sense. */
  streaming: boolean;
  /** The conversation's language, so the engine transcribes it instead of guessing (F4 S3). */
  languageCode?: string;
}

/** Append a transcript to what the user already wrote, without losing their text (S6). */
function append(existing: string, transcript: string): string {
  const trimmed = existing.trimEnd();
  return trimmed === "" ? transcript : `${trimmed} ${transcript}`;
}

export function ChatComposer({
  value,
  onChange,
  onSend,
  onStop,
  busy,
  streaming,
  languageCode,
}: ChatComposerProps) {
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const handleTranscript = useCallback(
    (text: string) => {
      onChange(append(value, text));
      // The transcript is editable before sending: the caret goes there, nothing is sent.
      requestAnimationFrame(() => inputRef.current?.focus());
    },
    [onChange, value],
  );

  const voice = useVoiceInput({ languageCode, onTranscript: handleTranscript });
  const voiceBusy = voice.status !== "idle";
  const canSend = value.trim().length > 0 && !busy && !voiceBusy;

  const submit = () => {
    if (!canSend) return;
    onSend();
    inputRef.current?.focus();
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    // desing.md §6.1.2: Enter sends, Shift+Enter inserts a line break.
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  };

  const status =
    voice.status === "recording"
      ? "Escuchando…"
      : voice.status === "transcribing"
        ? "Transcribiendo…"
        : null;

  return (
    <div className="composer-stack">
      {status && (
        <p className="composer__status" aria-live="polite" role="status">
          <span className="composer__status-dot" aria-hidden="true" />
          {status}
        </p>
      )}

      {voice.error && (
        <p className="composer__error" role="alert">
          {voice.error.message}
          {voice.error.kind === "permissions" ? (
            <>
              {" "}
              La app no puede abrir esa configuración por vos.{" "}
              <button
                type="button"
                className="composer__link"
                onClick={() => void voice.start()}
                disabled={busy}
                title={busy ? "Esperá a que termine la respuesta para hablar" : undefined}
              >
                Reintentar micrófono
              </button>
            </>
          ) : (
            <>
              {" "}
              <button type="button" className="composer__link" onClick={() => void voice.retry()}>
                Reintentar
              </button>
            </>
          )}
        </p>
      )}

      {voice.notice && !voice.error && (
        <p className="composer__status" role="status" aria-live="polite">
          {voice.notice}
        </p>
      )}

      <div className="composer">
        <button
          type="button"
          className="composer__tool"
          disabled
          title="Adjuntar archivos no está soportado todavía"
          aria-label="Adjuntar archivo"
        >
          <Icon name="paperclip" size={19} />
        </button>

        <label className="visually-hidden" htmlFor="composer-input">
          Escribe o habla
        </label>
        <textarea
          id="composer-input"
          ref={inputRef}
          className="composer__input"
          placeholder="Escribe o habla…"
          rows={1}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={handleKeyDown}
        />

        <button
          type="button"
          className="composer__tool"
          disabled
          title="La conversación por voz en vivo llega en F7"
          aria-label="Iniciar voz en vivo"
        >
          <Icon name="headphones" size={19} />
        </button>

        {voice.status === "recording" ? (
          <>
            <button
              type="button"
              className="composer__tool composer__tool--recording"
              onClick={() => void voice.stop()}
              aria-pressed
              aria-label="Detener y transcribir"
              title="Detener y transcribir"
            >
              <span className="composer__recording-dot" aria-hidden="true" />
            </button>
            <button
              type="button"
              className="composer__link"
              onClick={() => void voice.cancel()}
            >
              Cancelar
            </button>
          </>
        ) : (
          <button
            type="button"
            className="composer__tool"
            onClick={() => void voice.start()}
            disabled={busy || voice.status === "transcribing"}
            title={
              busy
                ? "Esperá a que termine la respuesta para hablar"
                : "Grabar un mensaje de voz"
            }
            aria-label="Grabar mensaje de voz"
          >
            <Icon name="mic" size={19} />
          </button>
        )}

        {streaming && (
          <button
            type="button"
            className="composer__stop"
            onClick={onStop}
            aria-label="Detener la respuesta"
          >
            Detener
          </button>
        )}

        <button
          type="button"
          className="composer__send"
          onClick={submit}
          disabled={!canSend}
          aria-label="Enviar mensaje"
        >
          <Icon name="send" size={18} />
        </button>
      </div>
    </div>
  );
}
