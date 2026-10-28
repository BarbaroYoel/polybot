import { Link } from "react-router-dom";
import { Icon } from "../../components/Icon";
import { Notice } from "../../components/Notice";
import { EmptyState, ErrorState, LoadingState } from "../../components/States";
import { errorMessage } from "../../lib/api/client";
import { getProgress } from "../../lib/api/progress";
import type {
  FrequentError,
  Progress,
  ProgressHistoryEntry,
  ProgressSkill,
  ProgressSkillId,
} from "../../lib/api/types";
import { useActiveLanguage } from "../../lib/language";
import { useAsync } from "../../lib/useAsync";
import "../sections/SectionPage.css";
import "./progress.css";

const SKILL_LABELS: Record<ProgressSkillId, string> = {
  conversation: "Conversación",
  writing: "Escritura",
  vocabulary: "Vocabulario",
  reading: "Lectura",
  listening: "Escucha",
};

const shortDateFormatter = new Intl.DateTimeFormat("es", {
  day: "numeric",
  month: "short",
  year: "numeric",
});

const historyDateFormatter = new Intl.DateTimeFormat("es", {
  day: "numeric",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

/**
 * Reader's IANA zone, sent as `tz` so the server starts the weekly goal on Monday where the
 * reader lives. When the browser does not expose one, the API falls back to UTC.
 */
const TIME_ZONE = (() => {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || undefined;
  } catch {
    return undefined;
  }
})();

/** `at` and `last_at` are ISO 8601 UTC; an invalid or missing value never breaks the render. */
function formatDate(value: string | null, formatter: Intl.DateTimeFormat): string | null {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : formatter.format(date);
}

/** Activity label of one available skill. Counts activity, never mastery (ADR-018). */
function skillCountLabel(skill: ProgressSkill): string | null {
  if (!skill.available || skill.count === null) return null;
  const count = skill.count;

  switch (skill.id) {
    case "conversation":
      return count === 1 ? "1 conversación" : `${count} conversaciones`;
    case "writing":
      return count === 1 ? "1 respuesta enviada" : `${count} respuestas enviadas`;
    case "vocabulary":
      return count === 1 ? "1 término sugerido" : `${count} términos sugeridos`;
    case "reading":
      return count === 1 ? "1 lectura" : `${count} lecturas`;
    case "listening":
      return count === 1 ? "1 práctica de escucha" : `${count} prácticas de escucha`;
  }
}

/** Reading and listening do not record a signal yet, so the UI explains why instead of a zero. */
function unavailableReason(id: ProgressSkillId): string {
  switch (id) {
    case "reading":
      return "La lectura todavía no deja un registro en Polybot.";
    case "listening":
      return "La escucha todavía no deja un registro en Polybot.";
    default:
      return "Esta destreza todavía no deja un registro en Polybot.";
  }
}

/**
 * `true` once at least one real signal exists. All-zero counters with no errors and no history
 * is the honest empty state (F6 S8): the screen offers actions instead of fake progress.
 */
function hasRecordedActivity(progress: Progress): boolean {
  const { summary, skills, frequent_errors, history } = progress;
  if (summary.lessons_completed > 0 || summary.conversations > 0) return true;
  if (frequent_errors.length > 0 || history.length > 0) return true;
  return skills.some((skill) => skill.available && (skill.count ?? 0) > 0);
}

interface ProgressBarProps {
  current: number;
  total: number;
  label: string;
}

/** Accessible bar. Callers only render it when `total > 0`, so there is never a 0/0 measure. */
function ProgressBar({ current, total, label }: ProgressBarProps) {
  const percent = Math.min(100, Math.max(0, (current / total) * 100));

  return (
    <div
      className="progress-bar"
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={total}
      aria-valuenow={current}
      aria-label={label}
    >
      <span className="progress-bar__fill" style={{ width: `${percent}%` }} />
    </div>
  );
}

function ErrorRow({ error }: { error: FrequentError }) {
  const date = formatDate(error.last_at, shortDateFormatter);
  const times = error.count === 1 ? "1 vez" : `${error.count} veces`;

  return (
    <li className="progress-error">
      <div className="progress-error__head">
        <span className="progress-tag">
          {error.kind === "correction" ? "Del tutor" : "De una lección"}
        </span>
        {date && <span className="progress-error__date">{date}</span>}
      </div>

      {error.prompt && <p className="progress-error__prompt">Consigna: {error.prompt}</p>}

      <p className="progress-error__pair">
        <span className="progress-error__original">{error.original}</span>
        <span className="progress-error__arrow" aria-hidden="true">
          →
        </span>
        <span className="visually-hidden"> en lugar de </span>
        <span className="progress-error__expected">{error.expected}</span>
      </p>

      <p className="progress-error__meta">
        Repetido {times}
        {date ? ` · último registro el ${date}` : ""}
      </p>
    </li>
  );
}

function HistoryRow({ entry }: { entry: ProgressHistoryEntry }) {
  const isLesson = entry.kind === "lesson";
  const date = formatDate(entry.at, historyDateFormatter);

  let detail: string | null = null;
  if (isLesson && entry.correct !== null && entry.total !== null) {
    detail = `${entry.correct} de ${entry.total} correctas`;
  } else if (!isLesson && entry.message_count !== null) {
    detail =
      entry.message_count === 1 ? "1 mensaje" : `${entry.message_count} mensajes`;
  }

  return (
    <li>
      <Link
        className="progress-history__row"
        to={isLesson ? `/lessons/${entry.id}` : `/chat/${entry.id}`}
      >
        <span className="progress-history__icon" aria-hidden="true">
          <Icon name={isLesson ? "book" : "chat"} size={18} />
        </span>
        <span className="progress-history__main">
          <span className="progress-history__title">{entry.title}</span>
          <span className="progress-history__meta">
            {isLesson ? "Lección" : "Conversación"}
            {date ? ` · ${date}` : ""}
            {detail ? ` · ${detail}` : ""}
          </span>
        </span>
        <span className="progress-history__go" aria-hidden="true">
          <Icon name="arrowRight" size={16} />
        </span>
      </Link>
    </li>
  );
}

/**
 * `/progress` (desing.md §6.5, F6 S1–S8): summary of the active language, the three skills with
 * a real signal, recurring mistakes and the practice history. No minutes are shown because v0
 * does not record duration (ADR-018); the level is read-only and is edited in `/languages`.
 */
export function ProgressPage() {
  const {
    active,
    status: languageStatus,
    error: languageError,
    reload: reloadLanguages,
  } = useActiveLanguage();
  const progress = useAsync<Progress | null>(
    () => (active ? getProgress(active.id, TIME_ZONE) : Promise.resolve(null)),
    [active?.id],
  );

  if (languageStatus === "loading" && !active) {
    return (
      <div className="page">
        <LoadingState label="Cargando tu idioma…" />
      </div>
    );
  }

  if (languageStatus === "error" && !active) {
    return (
      <div className="page">
        <ErrorState
          title="No pudimos cargar tus idiomas"
          description={errorMessage(languageError)}
          action={
            <button type="button" className="progress-btn" onClick={reloadLanguages}>
              Reintentar
            </button>
          }
        />
      </div>
    );
  }

  if (!active) {
    return (
      <div className="page">
        <EmptyState
          title="Todavía no hay un idioma activo"
          description="El progreso pertenece al idioma activo: cada idioma conserva sus conversaciones, lecciones y correcciones. Elige uno en Mis idiomas y su resumen aparece acá."
          action={
            <Link className="progress-btn" to="/languages">
              Ir a Mis idiomas
            </Link>
          }
        />
      </div>
    );
  }

  if (progress.status === "loading") {
    return (
      <div className="page">
        <LoadingState label={`Cargando el progreso en ${active.name}…`} />
      </div>
    );
  }

  if (progress.status === "error") {
    return (
      <div className="page">
        <ErrorState
          title="No pudimos cargar tu progreso"
          description={errorMessage(progress.error)}
          action={
            <button type="button" className="progress-btn" onClick={progress.reload}>
              Reintentar
            </button>
          }
        />
      </div>
    );
  }

  const data = progress.data;
  if (!data) {
    return (
      <div className="page">
        <EmptyState
          title="Todavía no hay datos suficientes"
          description="El progreso sale de lo que ya hiciste: conversaciones con mensajes, lecciones enviadas y correcciones del tutor. Cuando practiques, esta pantalla se llena sola."
          action={
            <div className="progress__actions">
              <Link className="progress-btn progress-btn--primary" to="/">
                Empezar a conversar
              </Link>
              <Link className="progress-btn" to="/lessons">
                Ver lecciones
              </Link>
            </div>
          }
        />
      </div>
    );
  }

  if (!hasRecordedActivity(data)) {
    return (
      <div className="page">
        <EmptyState
          title="Todavía no hay datos suficientes"
          description="El progreso sale de lo que ya hiciste en este idioma: conversaciones con mensajes, lecciones enviadas y correcciones del tutor. No estimamos ni inventamos métricas que no estén registradas."
          action={
            <div className="progress__actions">
              <Link className="progress-btn progress-btn--primary" to="/">
                Empezar a conversar
              </Link>
              <Link className="progress-btn" to="/lessons">
                Ver lecciones
              </Link>
            </div>
          }
        />
      </div>
    );
  }

  const { language, summary, skills, frequent_errors: errors, history } = data;
  const weekly = summary.weekly_goal;

  return (
    <div className="page progress">
      <header className="page__head">
        <div>
          <h1 className="page__title">Progreso</h1>
          <p className="page__description">
            Tu actividad registrada en {language.name}: qué practicaste, qué se repite y qué
            conviene repasar. El nivel es un dato de tu perfil, no una evaluación automática.
          </p>
        </div>
        <span className="page__phase">
          {language.name} · {summary.level}
        </span>
      </header>

      <Notice>
        Estos números cuentan actividad registrada, no dominio del idioma. La v0 solo muestra lo
        que queda guardado: no estima ni inventa métricas.
      </Notice>

      <section className="progress-section" aria-labelledby="progress-summary-title">
        <header className="progress-section__head">
          <h2 className="progress-section__title" id="progress-summary-title">
            Resumen de {language.name}
          </h2>
          <p className="progress-section__intro">
            Lo que ya quedó guardado en este idioma. Nada de acá se calcula con estimaciones.
          </p>
        </header>

        <div className="progress-summary">
          <article className="progress-card">
            <h3 className="progress-card__title">Nivel</h3>
            <p className="progress-card__value">
              <span className="progress-level">{summary.level}</span>
            </p>
            <p className="progress-card__note">
              Es el nivel guardado en tu perfil. Se cambia en{" "}
              <Link className="progress__link" to="/languages">
                Mis idiomas
              </Link>{" "}
              con una acción explícita.
            </p>
          </article>

          <article className="progress-card">
            <h3 className="progress-card__title">Lecciones completadas</h3>
            <p className="progress-card__value">
              {summary.lessons_completed} de {summary.lessons_total}
            </p>
            {summary.lessons_total > 0 ? (
              <>
                <ProgressBar
                  current={summary.lessons_completed}
                  total={summary.lessons_total}
                  label={`Lecciones completadas: ${summary.lessons_completed} de ${summary.lessons_total}`}
                />
                <p className="progress-card__note">
                  Cuenta una lección cuando tiene al menos un intento aprobado.
                </p>
              </>
            ) : (
              <p className="progress-card__note">
                El catálogo de este idioma todavía no tiene lecciones.
              </p>
            )}
          </article>

          <article className="progress-card">
            <h3 className="progress-card__title">Meta semanal</h3>
            <p className="progress-card__value">
              {weekly.conversations} de {weekly.target} conversaciones
            </p>
            {weekly.target > 0 ? (
              <>
                <ProgressBar
                  current={weekly.conversations}
                  total={weekly.target}
                  label={`Meta semanal: ${weekly.conversations} de ${weekly.target} conversaciones`}
                />
                <p className="progress-card__note">
                  Conversaciones con al menos un mensaje desde el lunes en tu zona horaria.
                </p>
              </>
            ) : (
              <p className="progress-card__note">
                La meta semanal de este idioma no tiene un objetivo configurado todavía.
              </p>
            )}
          </article>
        </div>
      </section>

      <section className="progress-section" aria-labelledby="progress-skills-title">
        <header className="progress-section__head">
          <h2 className="progress-section__title" id="progress-skills-title">
            Destrezas
          </h2>
          <p className="progress-section__intro">
            Cada destreza muestra la actividad que Polybot ya registra. Lectura y escucha todavía
            no tienen señal: no se muestran como un cero medido.
          </p>
        </header>

        <ul className="progress-skills">
          {skills.map((skill) => {
            const countLabel = skillCountLabel(skill);
            const lastAt = formatDate(skill.last_at, shortDateFormatter);

            return (
              <li
                className={`progress-skill${skill.available ? "" : " progress-skill--unavailable"}`}
                key={skill.id}
              >
                <h3 className="progress-skill__title">{SKILL_LABELS[skill.id]}</h3>
                {skill.available ? (
                  <>
                    <p className="progress-skill__count">
                      {countLabel ?? "Sin datos todavía"}
                    </p>
                    {skill.count === 0 ? (
                      <p className="progress-skill__meta">
                        Todavía no registramos actividad de esta destreza.
                      </p>
                    ) : (
                      lastAt && (
                        <p className="progress-skill__meta">Último registro: {lastAt}</p>
                      )
                    )}
                  </>
                ) : (
                  <>
                    <p className="progress-skill__count">Sin datos todavía</p>
                    <p className="progress-skill__meta">{unavailableReason(skill.id)}</p>
                  </>
                )}
              </li>
            );
          })}
        </ul>
      </section>

      <section className="progress-section" aria-labelledby="progress-errors-title">
        <header className="progress-section__head">
          <h2 className="progress-section__title" id="progress-errors-title">
            Errores frecuentes
          </h2>
          <p className="progress-section__intro">
            Pares que se repitieron en las correcciones del tutor y en las respuestas de lección.
            Sirven para repasar, no para calificar.
          </p>
        </header>

        {errors.length === 0 ? (
          <p className="progress-inline-empty">
            Todavía no hay errores registrados. Aparecen cuando el tutor corrige algo o una
            respuesta de lección no coincide con la esperada.
          </p>
        ) : (
          <ul className="progress-errors">
            {errors.slice(0, 5).map((error, index) => (
              <ErrorRow error={error} key={`${error.kind}-${index}`} />
            ))}
          </ul>
        )}
      </section>

      <section className="progress-section" aria-labelledby="progress-history-title">
        <header className="progress-section__head">
          <h2 className="progress-section__title" id="progress-history-title">
            Historial
          </h2>
          <p className="progress-section__intro">
            Tus últimas prácticas y lecciones en este idioma, de la más reciente a la más antigua.
          </p>
        </header>

        {history.length === 0 ? (
          <p className="progress-inline-empty">
            Todavía no hay prácticas guardadas en este idioma. Cada lección enviada y cada
            conversación con mensajes aparece acá.
          </p>
        ) : (
          <ul className="progress-history">
            {history.slice(0, 10).map((entry) => (
              <HistoryRow entry={entry} key={`${entry.kind}-${entry.id}`} />
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
