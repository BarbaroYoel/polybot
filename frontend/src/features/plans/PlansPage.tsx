import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";
import { Icon } from "../../components/Icon";
import { Notice } from "../../components/Notice";
import { EmptyState, ErrorState, LoadingState } from "../../components/States";
import { errorMessage } from "../../lib/api/client";
import { adjustPlan, createPlan, getPlan } from "../../lib/api/plans";
import type { PlanSession, PlanSessionState, StudyPlan } from "../../lib/api/types";
import { useActiveLanguage } from "../../lib/language";
import { useAsync } from "../../lib/useAsync";
import "../sections/SectionPage.css";
import "./plans.css";

const FREQUENCIES = [1, 2, 3, 4, 5, 6, 7];

const SESSION_STATUS_LABELS: Record<PlanSessionState, string> = {
  pending: "Pendiente",
  in_progress: "En curso",
  completed: "Completada",
};

interface PlanForm {
  goal: string;
  frequency: number;
  daily_minutes: number;
}

const EMPTY_FORM: PlanForm = { goal: "", frequency: 2, daily_minutes: 20 };

const dateFormatter = new Intl.DateTimeFormat("es", {
  day: "numeric",
  month: "long",
  year: "numeric",
});

/** `adjusted_at` is ISO 8601 UTC; the note shows it in the reader's local time. */
function formatDate(value: string | null): string | null {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : dateFormatter.format(date);
}

function SessionStatusBadge({ status }: { status: PlanSessionState }) {
  return (
    <span className={`plan-badge plan-badge--${status}`}>
      {status === "completed" && <Icon name="check" size={13} />}
      {SESSION_STATUS_LABELS[status]}
    </span>
  );
}

/** Groups the schedule by week. The server already sorts by week and position. */
function byWeek(sessions: PlanSession[]): Array<[number, PlanSession[]]> {
  const weeks = new Map<number, PlanSession[]>();
  for (const session of sessions) {
    const list = weeks.get(session.week) ?? [];
    list.push(session);
    weeks.set(session.week, list);
  }
  return Array.from(weeks.entries());
}

/**
 * `/plans` (desing.md §6.3, F5 S3, S4): the goal, the configurable rhythm, the weekly schedule
 * and the state of every session derived from real attempts. The plan is only recalculated when
 * the user presses «Ajustar plan»; nothing here changes it by itself.
 */
export function PlansPage() {
  const {
    active,
    status: languageStatus,
    error: languageError,
    reload: reloadLanguages,
  } = useActiveLanguage();
  const planState = useAsync(
    () => (active ? getPlan(active.id) : Promise.resolve(null)),
    [active?.id],
  );

  // The plan returned by a create/adjust write is the newest server truth until the next load.
  const [saved, setSaved] = useState<{ languageId: string; plan: StudyPlan } | null>(null);
  const plan = saved && saved.languageId === active?.id ? saved.plan : planState.data?.plan ?? null;

  const [form, setForm] = useState<PlanForm>(EMPTY_FORM);
  const [creating, setCreating] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const [adjustDraft, setAdjustDraft] = useState<{ frequency: number; daily_minutes: number } | null>(
    null,
  );
  const [adjusting, setAdjusting] = useState(false);
  const [adjustError, setAdjustError] = useState<string | null>(null);

  const [notice, setNotice] = useState<string | null>(null);

  // A language switch starts a clean form: nothing typed for one language is sent to another.
  useEffect(() => {
    setSaved(null);
    setForm(EMPTY_FORM);
    setFormError(null);
    setAdjustDraft(null);
    setAdjustError(null);
    setNotice(null);
  }, [active?.id]);

  const goal = form.goal.trim();
  const createValid =
    goal.length > 0 &&
    goal.length <= 200 &&
    form.frequency >= 1 &&
    form.frequency <= 7 &&
    form.daily_minutes >= 5 &&
    form.daily_minutes <= 120;

  const openAdjust = () => {
    if (!plan) return;
    setAdjustError(null);
    setNotice(null);
    setAdjustDraft({ frequency: plan.frequency, daily_minutes: plan.daily_minutes });
  };

  const handleCreate = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!active || creating || !createValid) return;

    setCreating(true);
    setFormError(null);
    setNotice(null);
    try {
      const created = await createPlan({
        language_id: active.id,
        goal,
        frequency: form.frequency,
        daily_minutes: form.daily_minutes,
      });
      setSaved({ languageId: active.id, plan: created });
      setForm(EMPTY_FORM);
      setNotice("Creamos el plan. El cronograma ya está disponible abajo.");
    } catch (error: unknown) {
      // 409 (a plan already exists) and 422 (out of range) arrive with a Spanish message.
      setFormError(errorMessage(error));
    } finally {
      setCreating(false);
    }
  };

  const handleAdjust = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!plan || !adjustDraft || adjusting) return;
    // The button is disabled when nothing changed; the guard keeps a programmatic submit honest.
    if (
      adjustDraft.frequency === plan.frequency &&
      adjustDraft.daily_minutes === plan.daily_minutes
    ) {
      return;
    }

    setAdjusting(true);
    setAdjustError(null);
    setNotice(null);
    try {
      const updated = await adjustPlan(plan.id, {
        frequency: adjustDraft.frequency,
        daily_minutes: adjustDraft.daily_minutes,
      });
      setSaved({ languageId: plan.language_id, plan: updated });
      setAdjustDraft(null);
      setNotice("Ajustamos el plan: el cronograma se recalculó con la frecuencia nueva.");
    } catch (error: unknown) {
      setAdjustError(errorMessage(error));
    } finally {
      setAdjusting(false);
    }
  };

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
            <button type="button" className="plan-btn" onClick={reloadLanguages}>
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
          description="Cada plan pertenece al idioma activo. Elige uno en Mis idiomas y su plan aparece acá."
          action={
            <Link className="plan-btn" to="/languages">
              Ir a Mis idiomas
            </Link>
          }
        />
      </div>
    );
  }

  if (planState.status === "loading") {
    return (
      <div className="page">
        <LoadingState label={`Cargando el plan en ${active.name}…`} />
      </div>
    );
  }

  if (planState.status === "error") {
    return (
      <div className="page">
        <ErrorState
          title="No pudimos cargar el plan"
          description={errorMessage(planState.error)}
          action={
            <button type="button" className="plan-btn" onClick={planState.reload}>
              Reintentar
            </button>
          }
        />
      </div>
    );
  }

  const adjusted = plan ? formatDate(plan.adjusted_at) : null;
  const adjustChanged =
    Boolean(plan) &&
    Boolean(adjustDraft) &&
    (adjustDraft?.frequency !== plan?.frequency ||
      adjustDraft?.daily_minutes !== plan?.daily_minutes);

  return (
    <div className="page plans">
      <header className="page__head">
        <div>
          <h1 className="page__title">Planes de estudio</h1>
          <p className="page__description">
            Un objetivo transformado en un cronograma por semanas. El estado de cada sesión sale de
            tus intentos en la lección; el plan solo se recalcula cuando lo ajustas vos.
          </p>
        </div>
        <span className="page__phase">
          {active.name} · {active.level}
        </span>
      </header>

      {notice && <Notice live>{notice}</Notice>}

      {plan === null ? (
        <section className="plan-create" aria-labelledby="plan-create-title">
          <h2 className="plan-create__title" id="plan-create-title">
            Crear un plan
          </h2>
          <p className="plan-create__intro">
            Define el objetivo y el ritmo de estudio. El cronograma se genera con el catálogo de
            lecciones del idioma activo.
          </p>
          <form className="plan-form" onSubmit={(event) => void handleCreate(event)}>
            <div className="plan-form__field">
              <label className="plan-form__label" htmlFor="plan-goal">
                Objetivo
              </label>
              <input
                id="plan-goal"
                className="plan-form__input"
                type="text"
                value={form.goal}
                onChange={(event) =>
                  setForm((current) => ({ ...current, goal: event.target.value }))
                }
                maxLength={200}
                placeholder="Por ejemplo: pasar de A1 a B1 en francés"
                autoComplete="off"
                disabled={creating}
              />
              <p className="plan-form__hint">
                Qué querés lograr. El objetivo queda fijo: al ajustar el plan solo cambian la
                frecuencia y el tiempo diario.
              </p>
            </div>

            <div className="plan-form__row">
              <div className="plan-form__field">
                <label className="plan-form__label" htmlFor="plan-frequency">
                  Frecuencia
                </label>
                <select
                  id="plan-frequency"
                  className="plan-form__input"
                  value={form.frequency}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      frequency: Number(event.target.value),
                    }))
                  }
                  disabled={creating}
                >
                  {FREQUENCIES.map((frequency) => (
                    <option key={frequency} value={frequency}>
                      {frequency} {frequency === 1 ? "sesión" : "sesiones"} por semana
                    </option>
                  ))}
                </select>
              </div>

              <div className="plan-form__field">
                <label className="plan-form__label" htmlFor="plan-minutes">
                  Tiempo diario
                </label>
                <input
                  id="plan-minutes"
                  className="plan-form__input"
                  type="number"
                  min={5}
                  max={120}
                  step={5}
                  value={form.daily_minutes}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      daily_minutes: Number(event.target.value),
                    }))
                  }
                  disabled={creating}
                />
                <p className="plan-form__hint">Entre 5 y 120 minutos por día.</p>
              </div>
            </div>

            {formError && <Notice live>{formError}</Notice>}

            <div className="plan-form__actions">
              <button
                type="submit"
                className="plan-btn plan-btn--primary"
                disabled={creating || !createValid}
              >
                {creating ? "Creando…" : "Crear plan"}
              </button>
            </div>
          </form>
        </section>
      ) : (
        <>
          <section className="plan" aria-labelledby="plan-goal">
            <h2 className="plan__goal" id="plan-goal">
              {plan.goal}
            </h2>

            <dl className="plan__metrics">
              <div>
                <dt>Frecuencia</dt>
                <dd>
                  {plan.frequency} {plan.frequency === 1 ? "sesión" : "sesiones"} por semana
                </dd>
              </div>
              <div>
                <dt>Tiempo diario</dt>
                <dd>{plan.daily_minutes} min</dd>
              </div>
              <div>
                <dt>Semanas</dt>
                <dd>{plan.weeks}</dd>
              </div>
            </dl>

            {adjusted && <p className="plan__adjusted">Ajustado el {adjusted}.</p>}

            <div className="plan__actions">
              {plan.sessions.length === 0 ? (
                <p className="plan__done">
                  Este plan todavía no tiene sesiones: el catálogo del idioma no tiene lecciones.{" "}
                  <Link className="plan__inline-link" to="/lessons">
                    Ver el catálogo
                  </Link>
                  .
                </p>
              ) : plan.next_session ? (
                <Link
                  className="plan-btn plan-btn--primary"
                  to={`/lessons/${plan.next_session.lesson_id}`}
                >
                  Continuar plan
                  <Icon name="arrowRight" size={16} />
                </Link>
              ) : (
                <p className="plan__done">
                  Todas las sesiones están completadas. Puedes repasar cualquiera desde el
                  cronograma.
                </p>
              )}
              <button type="button" className="plan-btn" onClick={openAdjust}>
                Ajustar plan
              </button>
            </div>

            <p className="plan__rule">
              El plan solo se recalcula cuando usas «Ajustar plan»; nada lo cambia por su cuenta.
            </p>
          </section>

          {adjustDraft && (
            <form
              className="plan-adjust"
              aria-labelledby="plan-adjust-title"
              onSubmit={(event) => void handleAdjust(event)}
            >
              <h2 className="plan-adjust__title" id="plan-adjust-title">
                Ajustar plan
              </h2>
              <p className="plan-adjust__goal">
                Objetivo: <strong>{plan.goal}</strong>. El objetivo no se ajusta: es lo que pediste
                al crear el plan.
              </p>

              <div className="plan-form__row">
                <div className="plan-form__field">
                  <label className="plan-form__label" htmlFor="adjust-frequency">
                    Frecuencia
                  </label>
                  <select
                    id="adjust-frequency"
                    className="plan-form__input"
                    value={adjustDraft.frequency}
                    onChange={(event) =>
                      setAdjustDraft((current) =>
                        current
                          ? { ...current, frequency: Number(event.target.value) }
                          : current,
                      )
                    }
                    disabled={adjusting}
                  >
                    {FREQUENCIES.map((frequency) => (
                      <option key={frequency} value={frequency}>
                        {frequency} {frequency === 1 ? "sesión" : "sesiones"} por semana
                      </option>
                    ))}
                  </select>
                </div>

                <div className="plan-form__field">
                  <label className="plan-form__label" htmlFor="adjust-minutes">
                    Tiempo diario
                  </label>
                  <input
                    id="adjust-minutes"
                    className="plan-form__input"
                    type="number"
                    min={5}
                    max={120}
                    step={5}
                    value={adjustDraft.daily_minutes}
                    onChange={(event) =>
                      setAdjustDraft((current) =>
                        current
                          ? { ...current, daily_minutes: Number(event.target.value) }
                          : current,
                      )
                    }
                    disabled={adjusting}
                  />
                  <p className="plan-form__hint">Entre 5 y 120 minutos por día.</p>
                </div>
              </div>

              {adjustError && <Notice live>{adjustError}</Notice>}

              <div className="plan-form__actions">
                <button
                  type="submit"
                  className="plan-btn plan-btn--primary"
                  disabled={adjusting || !adjustChanged}
                >
                  {adjusting ? "Guardando…" : "Guardar ajuste"}
                </button>
                <button
                  type="button"
                  className="plan-btn"
                  onClick={() => {
                    setAdjustDraft(null);
                    setAdjustError(null);
                  }}
                  disabled={adjusting}
                >
                  Cancelar
                </button>
              </div>
            </form>
          )}

          <section className="plan__schedule" aria-labelledby="plan-schedule-title">
            <header className="plan__schedule-head">
              <h2 className="plan__schedule-title" id="plan-schedule-title">
                Cronograma
              </h2>
              <p className="plan__schedule-note">
                El cronograma se cuenta en semanas desde que creaste el plan. Cada sesión abre su
                lección.
              </p>
            </header>

            {plan.sessions.length === 0 ? (
              <EmptyState
                title="El cronograma todavía está vacío"
                description="El catálogo de este idioma no tiene lecciones, así que el plan se creó sin sesiones. Cuando el catálogo tenga lecciones, ajusta el plan para regenerarlo."
              />
            ) : (
              <ol className="plan__weeks">
                {byWeek(plan.sessions).map(([week, sessions]) => (
                  <li className="plan__week" key={week}>
                    <h3 className="plan__week-title">Semana {week}</h3>
                    <ol className="plan__sessions">
                      {sessions.map((session) => (
                        <li key={session.id}>
                          <Link className="plan__session" to={`/lessons/${session.lesson_id}`}>
                            <span className="plan__session-index" aria-hidden="true">
                              {session.position + 1}
                            </span>
                            <span className="plan__session-main">
                              <span className="plan__session-title">{session.lesson_title}</span>
                            </span>
                            <SessionStatusBadge status={session.status} />
                            <span className="plan__session-go" aria-hidden="true">
                              <Icon name="arrowRight" size={16} />
                            </span>
                          </Link>
                        </li>
                      ))}
                    </ol>
                  </li>
                ))}
              </ol>
            )}
          </section>
        </>
      )}
    </div>
  );
}
