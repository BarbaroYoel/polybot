import { Link } from "react-router-dom";
import { Icon } from "../../components/Icon";
import { Notice } from "../../components/Notice";
import { EmptyState, ErrorState, LoadingState } from "../../components/States";
import { errorMessage } from "../../lib/api/client";
import { getLessonCatalog } from "../../lib/api/lessons";
import type { LessonCatalog, LessonUnitKind } from "../../lib/api/types";
import { useActiveLanguage } from "../../lib/language";
import { useAsync } from "../../lib/useAsync";
import "../sections/SectionPage.css";
import "./lessons.css";
import { LessonStatusBadge, unitKindLabel } from "./lessonUi";

const UNIT_KINDS: LessonUnitKind[] = [
  "vocabulary",
  "grammar",
  "pronunciation",
  "listening",
  "situational",
];

function catalogTotals(catalog: LessonCatalog): { total: number; completed: number } {
  let total = 0;
  let completed = 0;
  for (const unit of catalog.units) {
    for (const lesson of unit.lessons) {
      total += 1;
      if (lesson.status === "completed") completed += 1;
    }
  }
  return { total, completed };
}

/**
 * `/lessons` (desing.md §6.2, F5 S1): the catalog of the active language with «Continuar
 * aprendiendo». Both the next lesson and every lesson state come from the API; the screen never
 * invents a lesson or a progress value (S5, S6, S8).
 */
export function LessonsPage() {
  const {
    active,
    status: languageStatus,
    error: languageError,
    reload: reloadLanguages,
  } = useActiveLanguage();
  const catalog = useAsync<LessonCatalog | null>(
    () => (active ? getLessonCatalog(active.id) : Promise.resolve(null)),
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
            <button type="button" className="lesson-btn" onClick={reloadLanguages}>
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
          description="Las lecciones pertenecen al idioma activo. Elige uno en Mis idiomas y su catálogo aparece acá."
          action={
            <Link className="lesson-btn" to="/languages">
              Ir a Mis idiomas
            </Link>
          }
        />
      </div>
    );
  }

  if (catalog.status === "loading") {
    return (
      <div className="page">
        <LoadingState label={`Cargando las lecciones en ${active.name}…`} />
      </div>
    );
  }

  if (catalog.status === "error") {
    return (
      <div className="page">
        <ErrorState
          title="No pudimos cargar las lecciones"
          description={errorMessage(catalog.error)}
          action={
            <button type="button" className="lesson-btn" onClick={catalog.reload}>
              Reintentar
            </button>
          }
        />
      </div>
    );
  }

  const data = catalog.data;
  if (!data) {
    return (
      <div className="page">
        <EmptyState
          title="Este idioma todavía no tiene lecciones"
          description="El catálogo es contenido de ejemplo sembrado en la base local y todavía no incluye lecciones para el idioma activo."
          action={
            <Link className="lesson-btn" to="/languages">
              Elegir otro idioma
            </Link>
          }
        />
      </div>
    );
  }

  const totals = catalogTotals(data);

  // A seeded catalog can exist without lessons for this language: say so instead of an empty list.
  if (totals.total === 0) {
    return (
      <div className="page">
        <EmptyState
          title="Este idioma todavía no tiene lecciones"
          description="El catálogo es contenido de ejemplo sembrado en la base local y todavía no incluye lecciones para este idioma. Puedes activar otro idioma mientras se carga su catálogo."
          action={
            <Link className="lesson-btn" to="/languages">
              Elegir otro idioma
            </Link>
          }
        />
      </div>
    );
  }

  const next = data.next_lesson;
  const nextUnit = next ? data.units.find((unit) => unit.id === next.unit_id) : undefined;
  const presentKinds = new Set(data.units.map((unit) => unit.kind));
  const missingKinds = UNIT_KINDS.filter((kind) => !presentKinds.has(kind));

  return (
    <div className="page lessons">
      <header className="page__head">
        <div>
          <h1 className="page__title">Lecciones</h1>
          <p className="page__description">
            Unidades cortas con práctica y feedback del tutor. El estado de cada lección sale de
            tus intentos guardados, no de un contador de la interfaz.
          </p>
        </div>
        <span className="page__phase">
          {data.language_name} · {data.level}
        </span>
      </header>

      <Notice>
        Catálogo de ejemplo sembrado en la base local: no es un currículo validado.
        {missingKinds.length > 0 && (
          <>
            {" "}
            Todavía no hay unidades de{" "}
            {missingKinds.map((kind) => unitKindLabel(kind).toLowerCase()).join(", ")}.
          </>
        )}
      </Notice>

      <section className="lesson-start" aria-labelledby="lesson-start-title">
        <div className="lesson-start__head">
          <h2 className="lesson-start__title" id="lesson-start-title">
            Continuar aprendiendo
          </h2>
          {totals.total > 0 && (
            <p className="lesson-start__count">
              {totals.completed} de {totals.total} completadas
            </p>
          )}
        </div>

        {next ? (
          <>
            <p className="lesson-start__lesson">{next.title}</p>
            <p className="lesson-start__meta">
              {nextUnit ? `${unitKindLabel(nextUnit.kind)} · ` : ""}
              {next.difficulty} · {next.estimated_minutes} min
            </p>
            <div className="lesson-start__actions">
              <Link className="lesson-btn lesson-btn--primary" to={`/lessons/${next.id}`}>
                {next.status === "in_progress" ? "Retomar lección" : "Empezar lección"}
                <Icon name="arrowRight" size={16} />
              </Link>
              <LessonStatusBadge status={next.status} />
            </div>
          </>
        ) : (
          <p className="lesson-start__empty">
            Completaste las {totals.total} lecciones de este catálogo. Puedes repasar cualquiera
            desde las unidades de abajo.
          </p>
        )}
      </section>

      <div className="lessons__units">
        {data.units.map((unit) => (
          <section className="unit" key={unit.id} aria-labelledby={`unit-${unit.id}`}>
            <header className="unit__head">
              <p className="unit__kind">{unitKindLabel(unit.kind)}</p>
              <h2 className="unit__title" id={`unit-${unit.id}`}>
                {unit.title}
              </h2>
              <p className="unit__description">{unit.description}</p>
            </header>

            {unit.lessons.length === 0 ? (
              <p className="unit__empty">Esta unidad todavía no tiene lecciones.</p>
            ) : (
              <ol className="unit__lessons">
                {unit.lessons.map((lesson) => (
                  <li key={lesson.id}>
                    <Link className="lesson-row" to={`/lessons/${lesson.id}`}>
                      <span className="lesson-row__index" aria-hidden="true">
                        {lesson.position + 1}
                      </span>
                      <span className="lesson-row__main">
                        <span className="lesson-row__title">{lesson.title}</span>
                        <span className="lesson-row__meta">
                          {unitKindLabel(unit.kind)} · {lesson.difficulty} ·{" "}
                          {lesson.estimated_minutes} min
                        </span>
                      </span>
                      <LessonStatusBadge status={lesson.status} />
                      <span className="lesson-row__go" aria-hidden="true">
                        <Icon name="arrowRight" size={16} />
                      </span>
                    </Link>
                  </li>
                ))}
              </ol>
            )}
          </section>
        ))}
      </div>
    </div>
  );
}
