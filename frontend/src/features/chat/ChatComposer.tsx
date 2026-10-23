import { useRef } from "react";
import type { KeyboardEvent } from "react";
import { Icon } from "../../components/Icon";

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
}

export function ChatComposer({
  value,
  onChange,
  onSend,
  onStop,
  busy,
  streaming,
}: ChatComposerProps) {
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const canSend = value.trim().length > 0 && !busy;

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

  return (
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

      <button
        type="button"
        className="composer__tool"
        disabled
        title="El micrófono llega con el backend de voz (F4)"
        aria-label="Grabar voz"
      >
        <Icon name="mic" size={19} />
      </button>

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
  );
}
