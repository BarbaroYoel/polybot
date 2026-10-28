import { useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";
import { Icon } from "../../components/Icon";
import { Notice } from "../../components/Notice";
import { EmptyState, ErrorState, LoadingState } from "../../components/States";
import { errorMessage } from "../../lib/api/client";
import { translateText } from "../../lib/api/translate";
import type { TranslateResult } from "../../lib/api/translate";
import type { LanguageProfile } from "../../lib/api/types";
import { useActiveLanguage } from "../../lib/language";
import "../sections/SectionPage.css";
import "./translate.css";
import { useInterpreter } from "./useInterpreter";
import type { InterpreterStatus } from "./useInterpreter";

/** The contract's limit for one translation request (docs/api-contract.md §5). */
const MAX_TEXT = 4000;

const displayNames =
  typeof Intl !== "undefined" && "DisplayNames" in Intl
    ? new Intl.DisplayNames(["es"], { type: "language" })
    : null;

function languageLabel(code: string): string {
  const name = displayNames?.of(code) ?? code.toUpperCase();
  return name.charAt(0).toUpperCase() + name.slice(1);
}

function languageOptions(languages: LanguageProfile[]): string[] {
  const codes = new Set<string>();
  for (const language of languages) {
    codes.add(language.code);
    codes.add(language.explanation_language);
  }
  // The explanation language of the seeded profiles is Spanish; keep it available even if the
  // user only has one learning language.
  codes.add("es");
  return [...codes].filter(Boolean);
}

/**
 * `/translate` text mode (desing.md §6.4, F7 T4). The request is the stateless `POST /translate`
 * (ADR-014): nothing is stored, and the copy button is the only action on the result.
 */
function TextTranslator() {
  const { status, languages, active, error: languageError, reload } = useActiveLanguage();
  const [source, setSource] = useState("");
  const [target, setTarget] = useState("");
  const [text, setText] = useState("");
  const [result, setResult] = useState<TranslateResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const initialized = useRef(false);

  // The first real profile seeds the direction; after that the user owns the selectors.
  useEffect(() => {
    if (!active || initialized.current) return;
    initialized.current = true;
    setSource(active.code);
    setTarget(active.explanation_language);
  }, [active]);

  const targets = useMemo(() => languageOptions(languages), [languages]);

  const translate = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmed = text.trim();
    if (!trimmed || !target || busy) return;

    setBusy(true);
    setError(null);
    setCopied(false);
    try {
      const response = await translateText({
        text: trimmed,
        target,
        ...(source ? { source } : {}),
      });
      setResult(response);
    } catch (caught: unknown) {
      setResult(null);
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  };

  const copy = async () => {
    if (!result) return;
    try {
      await navigator.clipboard.writeText(result.translation);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setError("No pudimos copiar la traducción. Selecciona el texto y cópialo a mano.");
    }
  };

  if (status === "loading" && languages.length === 0) {
    return <LoadingState label="Cargando tus idiomas…" />;
  }

  if (status === "error" && languages.length === 0) {
    return (
      <ErrorState
        title="No pudimos cargar tus idiomas"
        description={errorMessage(languageError)}
        action={
          <button type="button" className="translate__button" onClick={reload}>
            Reintentar
          </button>
        }
      />
    );
  }

  if (languages.length === 0) {
    return (
      <EmptyState
        title="Todavía no hay idiomas para traducir"
        description="Agrega al menos un idioma para elegir el origen y el destino de la traducción."
        action={
          <Link className="translate__button" to="/languages">
            Ir a Mis idiomas
          </Link>
        }
      />
    );
  }

  return (
    <form className="translate__panel" onSubmit={translate}>
      <div className="translate__selectors">
        <label className="translate__field">
          <span>Idioma de origen</span>
          <select
            className="translate__select"
            value={source}
            onChange={(event) => {
              setSource(event.target.value);
              setResult(null);
            }}
          >
            <option value="">Detectar idioma</option>
            {languages.map((language) => (
              <option key={language.id} value={language.code}>
                {language.name}
              </option>
            ))}
          </select>
        </label>
        <label className="translate__field">
          <span>Idioma de destino</span>
          <select
            className="translate__select"
            value={target}
            onChange={(event) => {
              setTarget(event.target.value);
              setResult(null);
            }}
            required
          >
            {targets.map((code) => (
              <option key={code} value={code}>
                {languageLabel(code)}
              </option>
            ))}
          </select>
        </label>
      </div>

      <label className="translate__field">
        <span>Texto a traducir</span>
        <textarea
          className="translate__textarea"
          value={text}
          onChange={(event) => {
            setText(event.target.value);
            setResult(null);
            setCopied(false);
          }}
          maxLength={MAX_TEXT}
          rows={6}
          placeholder="Escribe o pega el texto que quieres traducir…"
        />
      </label>

      {error && <Notice>{error}</Notice>}

      <div className="translate__actions">
        <span className="translate__count">
          {text.length}/{MAX_TEXT}
        </span>
        <button
          type="submit"
          className="translate__button translate__button--primary"
          disabled={!text.trim() || !target || busy}
        >
          {busy ? "Traduciendo…" : "Traducir"}
        </button>
      </div>

      {result && (
        <section className="translate__result" aria-live="polite">
          <div className="translate__result-head">
            <h2 className="translate__result-title">Traducción</h2>
            <button type="button" className="translate__button" onClick={copy}>
              {copied ? "Copiado" : "Copiar"}
            </button>
          </div>
          <p className="translate__result-text">{result.translation}</p>
          <p className="translate__meta">
            {source ? `Desde ${languageLabel(source)}` : "Origen detectado por el proveedor"} · hacia{" "}
            {languageLabel(target)}
          </p>
        </section>
      )}

      <p className="translate__hint">
        La traducción de texto no se guarda: el servidor la devuelve y la olvida. El audio de la
        traducción queda para otra fase.
      </p>
    </form>
  );
}

const STATUS_LABELS: Record<InterpreterStatus, string> = {
  idle: "Listo para escuchar",
  connecting: "Conectando…",
  listening: "Escuchando…",
  processing: "Procesando…",
  stopped: "Detenido",
  error: "Error",
};

function formatTime(ms: number): string {
  const total = Math.max(0, Math.round(ms / 1000));
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

/**
 * `/translate` live mode (desing.md §6.4, F7 T5). The microphone streams PCM to the WebSocket; the
 * screen keeps the ephemeral history and shows partial and final translations as they arrive.
 */
function InterpreterPanel() {
  const {
    status: languageStatus,
    languages,
    active,
    error: languageError,
    reload,
  } = useActiveLanguage();
  const interpreter = useInterpreter();
  const [source, setSource] = useState("");
  const [target, setTarget] = useState("");
  const initialized = useRef(false);

  useEffect(() => {
    if (!active || initialized.current) return;
    initialized.current = true;
    setSource(active.code);
    setTarget(active.explanation_language);
  }, [active]);

  const targets = useMemo(() => languageOptions(languages), [languages]);
  const running =
    interpreter.status === "connecting" ||
    interpreter.status === "listening" ||
    interpreter.status === "processing";

  if (languageStatus === "loading" && languages.length === 0) {
    return <LoadingState label="Cargando tus idiomas…" />;
  }

  if (languageStatus === "error" && languages.length === 0) {
    return (
      <ErrorState
        title="No pudimos cargar tus idiomas"
        description={errorMessage(languageError)}
        action={
          <button type="button" className="translate__button" onClick={reload}>
            Reintentar
          </button>
        }
      />
    );
  }

  if (languages.length === 0) {
    return (
      <EmptyState
        title="Todavía no hay idiomas para interpretar"
        description="Agrega al menos un idioma para elegir el origen y el destino del intérprete."
        action={
          <Link className="translate__button" to="/languages">
            Ir a Mis idiomas
          </Link>
        }
      />
    );
  }

  return (
    <div className="translate__panel">
      <div className="translate__selectors">
        <label className="translate__field">
          <span>Idioma de origen</span>
          <select
            className="translate__select"
            value={source}
            onChange={(event) => setSource(event.target.value)}
            disabled={running}
          >
            <option value="">Detectar idioma</option>
            {languages.map((language) => (
              <option key={language.id} value={language.code}>
                {language.name}
              </option>
            ))}
          </select>
        </label>
        <label className="translate__field">
          <span>Idioma de destino</span>
          <select
            className="translate__select"
            value={target}
            onChange={(event) => setTarget(event.target.value)}
            disabled={running}
            required
          >
            {targets.map((code) => (
              <option key={code} value={code}>
                {languageLabel(code)}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="interpreter__bar">
        <span
          className={`interpreter__status interpreter__status--${interpreter.status}`}
          role="status"
          aria-live="polite"
        >
          <span className="interpreter__dot" aria-hidden="true" />
          {STATUS_LABELS[interpreter.status]}
        </span>

        <div className="interpreter__actions">
          {!running && (
            <button
              type="button"
              className="translate__button translate__button--primary"
              onClick={() => void interpreter.start(source || null, target)}
              disabled={!target}
            >
              <Icon name="mic" size={18} />
              Iniciar micrófono
            </button>
          )}
          {(interpreter.status === "connecting" || interpreter.status === "listening") && (
            <button type="button" className="translate__button" onClick={interpreter.stop}>
              Detener
            </button>
          )}
          {running && interpreter.status !== "processing" && (
            <button type="button" className="translate__button" onClick={interpreter.cancel}>
              Cancelar
            </button>
          )}
        </div>
      </div>

      <Notice live>
        La latencia y la precisión varían según el audio y la conexión. El audio no se guarda: se
        transcribe, se traduce y se descarta.
      </Notice>

      {interpreter.error && <Notice live>{interpreter.error}</Notice>}

      <section className="interpreter__transcript" aria-live="polite">
        {interpreter.segments.length === 0 && !interpreter.partialText && !interpreter.partialPending ? (
          <div className="interpreter__empty">
            <Icon name="mic" size={28} />
            <p>
              Inicia el micrófono y habla. La transcripción aparece por segmentos, con su traducción.
            </p>
          </div>
        ) : (
          <>
            {interpreter.segments.map((line) => (
              <article key={line.id} className="interpreter__segment">
                <p className="interpreter__original">{line.text}</p>
                <p className="interpreter__translation">
                  {line.translation ?? "Traduciendo…"}
                </p>
                <p className="interpreter__meta">
                  {line.language ? `${languageLabel(line.language)} · ` : ""}
                  {formatTime(line.startMs)}–{formatTime(line.endMs)}
                </p>
              </article>
            ))}

            {(interpreter.partialText || interpreter.partialPending) && (
              <article className="interpreter__segment interpreter__segment--live">
                <p className="interpreter__original">
                  {interpreter.partialText}
                  {interpreter.partialPending && (
                    <span className="interpreter__pending"> {interpreter.partialPending}</span>
                  )}
                </p>
                <p className="interpreter__translation">
                  {interpreter.partialTranslation || "Traduciendo…"}
                </p>
                <p className="interpreter__meta">En vivo · la traducción parcial es tentativa</p>
              </article>
            )}
          </>
        )}
      </section>

      <p className="translate__hint">
        El segmento cerrado manda: su traducción reemplaza a la parcial. No hay audio guardado ni
        historial al recargar.
      </p>
    </div>
  );
}

/**
 * `/translate` (desing.md §6.4, F7): two separate modes, text and live interpreter. The F7 text
 * slice is real; the interpreter arrives in T5.
 */
export function TranslatePage() {
  const [mode, setMode] = useState<"text" | "interpreter">("text");

  return (
    <div className="page translate">
      <header className="page__head">
        <div>
          <h1 className="page__title">Traducción en tiempo real</h1>
          <p className="page__description">
            Dos flujos separados: traducir texto e interpretar voz, sin mezclarlos con una lección.
          </p>
        </div>
        <span className="page__phase" title="Estado de esta vista">
          {mode === "text" ? "F7 · texto" : "F7 · intérprete"}
        </span>
      </header>

      <div className="translate__tabs" role="tablist" aria-label="Modo de traducción">
        <button
          type="button"
          role="tab"
          aria-selected={mode === "text"}
          className="translate__tab"
          onClick={() => setMode("text")}
        >
          Traducir texto
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={mode === "interpreter"}
          className="translate__tab"
          onClick={() => setMode("interpreter")}
        >
          Intérprete de voz
        </button>
      </div>

      {mode === "text" ? <TextTranslator /> : <InterpreterPanel />}
    </div>
  );
}
