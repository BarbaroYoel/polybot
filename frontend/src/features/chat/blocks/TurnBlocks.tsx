import { useState } from "react";
import type { FormEvent } from "react";
import { Icon } from "../../../components/Icon";
import { errorMessage } from "../../../lib/api/client";
import type { DrillResult, PracticeBlock } from "../../../lib/types";
import { useSpeech } from "../useSpeech";
import "./blocks.css";

interface TurnBlocksProps {
  blocks: PracticeBlock[];
  /** The conversation's language: the phrase is read with the right voice (F4 S3). */
  languageCode?: string;
  /**
   * Grades one drill. `undefined` while the turn is still open, so a half-written reply cannot be
   * answered; the API also refuses a block that is not stored yet.
   */
  onAnswer?: (blockId: string, answer: string) => Promise<DrillResult>;
}

/**
 * The practice blocks of one tutor turn (ADR-020, desing.md §6.1.2).
 *
 * Two rules keep this simple: a block never replaces the text of the reply, and an unknown kind is
 * shown as a notice instead of breaking the thread. The renderer only chooses how to draw a known
 * kind; the contract decided what a block is.
 */
export function TurnBlocks({ blocks, languageCode, onAnswer }: TurnBlocksProps) {
  if (blocks.length === 0) return null;

  return (
    <div className="blocks" aria-label="Práctica del turno">
      {blocks.map((block) => {
        if (block.kind === "phrase") {
          return <PhraseCard block={block} languageCode={languageCode} key={block.id} />;
        }
        if (block.kind === "drill") {
          return <DrillCard block={block} onAnswer={onAnswer} key={block.id} />;
        }
        return (
          <p className="blocks__unknown" key={block.id}>
            Este bloque de práctica todavía no se puede mostrar en esta versión.
          </p>
        );
      })}
    </div>
  );
}

/** A sentence worth hearing again: the audio is synthesized on demand, never stored (F4). */
function PhraseCard({
  block,
  languageCode,
}: {
  block: { id: string; kind: "phrase"; text: string };
  languageCode?: string;
}) {
  const speech = useSpeech({ text: block.text, languageCode });

  return (
    <section className="blocks__card" aria-label="Frase para practicar">
      <p className="blocks__title">Frase para practicar</p>
      <p className="blocks__phrase">{block.text}</p>

      <div className="blocks__actions">
        <button
          type="button"
          className="message__action"
          onClick={() => void speech.play(1)}
          disabled={speech.status === "loading"}
          aria-pressed={speech.status === "playing"}
          title={speech.status === "playing" ? "Detener la reproducción" : "Escuchar la frase"}
        >
          <Icon name="volume" size={15} />
          {speech.status === "playing" ? "Detener" : "Escuchar"}
        </button>
        <button
          type="button"
          className="message__action"
          onClick={() => void speech.play(0.75)}
          disabled={speech.status === "loading"}
          title="Escuchar la frase más despacio"
        >
          Más lento
        </button>
        {speech.status === "loading" && (
          <span className="blocks__status" aria-live="polite">
            Preparando el audio…
          </span>
        )}
        {speech.status === "playing" && (
          <span className="blocks__status" aria-live="polite">
            Reproduciendo…
          </span>
        )}
      </div>

      {speech.error && (
        <p className="blocks__error" role="alert">
          {speech.error}{" "}
          <button type="button" className="message__retry" onClick={() => void speech.play(1)}>
            Reintentar
          </button>
        </p>
      )}
    </section>
  );
}

/**
 * One question, graded by the API with the same rules as a lesson (ADR-017).
 *
 * The verdict is kept in this component: nothing is stored, so a reload asks the question again.
 * That is deliberate — the drill does not feed `/progress` in v1 (ADR-020, ADR-018).
 */
function DrillCard({
  block,
  onAnswer,
}: {
  block: { id: string; kind: "drill"; prompt: string };
  onAnswer?: (blockId: string, answer: string) => Promise<DrillResult>;
}) {
  const [answer, setAnswer] = useState("");
  const [status, setStatus] = useState<"idle" | "sending" | "error">("idle");
  const [result, setResult] = useState<DrillResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const sending = status === "sending";

  async function grade(): Promise<void> {
    const text = answer.trim();
    if (!onAnswer || !text || sending) return;

    setStatus("sending");
    setError(null);
    try {
      setResult(await onAnswer(block.id, text));
      setStatus("idle");
    } catch (cause) {
      setError(errorMessage(cause));
      setStatus("error");
    }
  }

  function submit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    void grade();
  }

  return (
    <section className="blocks__card" aria-label="Ejercicio del turno">
      <p className="blocks__title">Practicá lo del turno</p>
      <p className="blocks__prompt">{block.prompt}</p>

      <form className="blocks__form" onSubmit={submit}>
        <input
          className="blocks__input"
          type="text"
          value={answer}
          onChange={(event) => {
            setAnswer(event.target.value);
            if (status === "error") setError(null);
          }}
          placeholder="Escribí tu respuesta…"
          aria-label="Tu respuesta"
          autoComplete="off"
          spellCheck={false}
          disabled={sending || result?.correct === true}
        />
        <button
          type="submit"
          className="message__action"
          disabled={sending || !answer.trim() || result?.correct === true}
        >
          {sending ? "Comprobando…" : "Comprobar"}
        </button>
      </form>

      {result && (
        <p
          className={`blocks__result blocks__result--${result.correct ? "correct" : "wrong"}`}
          role="status"
        >
          {result.correct ? (
            "¡Correcto!"
          ) : (
            <>
              Todavía no. Se dice «{result.expected}».
            </>
          )}
          {result.explanation && <span className="blocks__note">{result.explanation}</span>}
        </p>
      )}

      {error && (
        <p className="blocks__error" role="alert">
          {error}{" "}
          <button type="button" className="message__retry" onClick={() => void grade()}>
            Reintentar
          </button>
        </p>
      )}
    </section>
  );
}
