import { useRef } from "react";
import type { KeyboardEvent } from "react";
import { Icon } from "../../components/Icon";

interface ChatComposerProps {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
}

export function ChatComposer({ value, onChange, onSend }: ChatComposerProps) {
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const canSend = value.trim().length > 0;

  const submit = () => {
    if (!canSend) return;
    onSend();
    inputRef.current?.focus();
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
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
