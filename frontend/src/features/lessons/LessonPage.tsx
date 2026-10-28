import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { Icon } from "../../components/Icon";
import { Notice } from "../../components/Notice";
import { EmptyState, ErrorState, LoadingState } from "../../components/States";
import { errorMessage } from "../../lib/api/client";
import { getLesson, submitLesson } from "../../lib/api/lessons";
import type { LessonDetail, LessonResult } from "../../lib/api/types";
import { useActiveLanguage } from "../../lib/language";
import { useAsync } from "../../lib/useAsync";
import "../sections/SectionPage.css";
import "./lessons.css";
import { LessonStatusBadge, unitKindLabel } from "./lessonUi";

/**
 * `/lessons/:lessonId` (desing.md §6.2, F5 S2): short content, a typed practice and the tutor's
 * closing feedback. Answers are only sent when the user submits the whole lesson; the result, the
 * mistakes and the next recommendation are the API's, not the UI's (S5, S8).
 */
export function LessonPage() {
  const { lessonId = "" } = useParams();
  const {
    active,
    status: languageStatus,
    error: languageError,
    reload: reloadLanguages,
  } = useActiveLanguage();
  // The active language guards the read: a lesson of another language is a 404, not a leak (S6).
  const detail = useAsync<LessonDetail | null>(
    () => (active ? getLesson(lessonId, active.id) : Promise.resolve(null)),
    [lessonId, active?.id],
  );

  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [result, setResult] = useState<LessonResult | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const resultHeading = useRef<HTMLHeadingElement>(null);

  // A different lesson or language starts a clean practice: no stale answers or result.
  useEffect(() => {
    setAnswers({});
    setResult(null);
    setSubmitError(null);
  }, [lessonId, active?.id]);

  useEffect(() => {
    if (result) resultHeading.current?.focus();
  }, [result]);

  const lesson = detail.data;
  const exercises = lesson?.exercises ?? [];
  const answered = exercises.filter((exercise) => (answers[exercise.id] ?? "").trim()).length;
  const complete = exercises.length > 0 && answered === exercises.length;

  const resetPractice = () => {
    setAnswers({});
    setResult(null);
    setSubmitError(null);
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!lesson || submitting || !complete) return;

    setSubmitting(true);
    setSubmitError(null);
    try {
      const graded = await submitLesson(
        lesson.id,
        exercises.map((exercise) => ({
          exercise_id: exercise.id,
          answer: (answers[exercise.id] ?? "").trim(),
        })),
      );
      setResult(graded);
    } catch (error: unknown) {
      // 422 `missing_lesson_answers` and provider/network failures all arrive with a message.
      setSubmitError(errorMessage(error));
    } finally {
      setSubmitting(false);
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
          description="Cada lección pertenece al idioma activo. Elige uno en Mis idiomas para practicarlo."
          action={
            <Link className="lesson-btn" to="/languages">
              Ir a Mis idiomas
            </Link>
          }
        />
      </div>
    );
  }

  if (detail.status === "loading") {
    return (
      <div className="page">
        <LoadingState label="Cargando la lección…" />
      </div>
    );
  }

  if (detail.status === "error") {
    const notFound = detail.error?.code === "lesson_not_found";
    return (
      <div className="page">
        {notFound ? (
          <EmptyState
            title="No encontramos esa lección"
            description="El enlace apunta a una lección que no existe en el idioma activo. Puede que pertenezca a otro idioma."
            action={
              <Link className="lesson-btn" to="/lessons">
                Volver al catálogo
              </Link>
            }
          />
        ) : (
          <ErrorState
            title="No pudimos cargar la lección"
            description={errorMessage(detail.error)}
            action={
              <button type="button" className="lesson-btn" onClick={detail.reload}>
                Reintentar
              </button>
            }
          />
        )}
      </div>
    );
  }

  if (!lesson) {
    return (
      <div className="page">
        <EmptyState
          title="No encontramos esa lección"
          description="El catálogo del idioma activo no tiene esta lección."
          action={
            <Link className="lesson-btn" to="/lessons">
              Volver al catálogo
            </Link>
          }
        />
      </div>
    );
  }

  return (
    <div className="page lesson">
      <Link className="lesson__back" to="/lessons">
        Volver a Lecciones
      </Link>

      <header className="page__head">
        <div>
          <p className="lesson__eyebrow">
            {lesson.unit_title} · {unitKindLabel(lesson.unit_kind)}
          </p>
          <h1 className="page__title">{lesson.title}</h1>
          <p className="page__description lesson__intro">{lesson.intro}</p>
        </div>
        <span className="page__phase">
          {lesson.difficulty} · {lesson.estimated_minutes} min
        </span>
      </header>

      <Notice>
        Respondé en {active.name}. La corrección no distingue mayúsculas ni puntuación, pero sí
        acentos.
      </Notice>

      {result ? (
        <section className="result" aria-labelledby="lesson-result-title">
          <header className="result__head">
            <h2 className="result__title" id="lesson-result-title" ref={resultHeading} tabIndex={-1}>
              Resultado
            </h2>
            <LessonStatusBadge status={result.completed ? "completed" : "in_progress"} />
          </header>
          <p className="result__score">
            {result.correct} de {result.total} respuestas correctas.{" "}
            {result.completed
              ? "La lección quedó completada y el intento está guardado."
              : "La lección queda en curso: repasa lo que sigue y vuelve a intentarlo."}
          </p>

          <div className="result__block">
            <h3 className="result__block-title">Errores relevantes</h3>
            {result.mistakes.length === 0 ? (
              <p className="result__empty">Ninguno: todas las respuestas salieron bien.</p>
            ) : (
              <ul className="result__mistakes">
                {result.mistakes.map((mistake) => (
                  <li className="result__mistake" key={mistake.exercise_id}>
                    <p className="result__prompt">{mistake.prompt}</p>
                    <dl className="result__compare">
                      <div>
                        <dt>Tu respuesta</dt>
                        <dd>{mistake.answer}</dd>
                      </div>
                      <div>
                        <dt>Respuesta esperada</dt>
                        <dd>{mistake.expected}</dd>
                      </div>
                    </dl>
                    <p className="result__explanation">{mistake.explanation}</p>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="result__block">
            <h3 className="result__block-title">Vocabulario nuevo</h3>
            {result.vocabulary.length === 0 ? (
              <p className="result__empty">Esta lección no agrega vocabulario nuevo.</p>
            ) : (
              <ul className="result__terms">
                {result.vocabulary.map((term) => (
                  <li className="result__term" key={`${term.term}-${term.translation}`}>
                    <span className="result__term-name">{term.term}</span>
                    <span className="result__term-translation">{term.translation}</span>
                    {term.note && <span className="result__term-note">{term.note}</span>}
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="result__block">
            <h3 className="result__block-title">Comentario del tutor</h3>
            {result.feedback ? (
              <p className="result__comment">{result.feedback}</p>
            ) : (
              <p className="result__empty">
                El tutor no dejó un comentario esta vez. La corrección de la lección ya está
                guardada.
              </p>
            )}
          </div>

          <div className="result__block">
            <h3 className="result__block-title">Próxima recomendación</h3>
            {result.next_lesson && result.next_lesson.id !== lesson.id ? (
              <Link className="result__next" to={`/lessons/${result.next_lesson.id}`}>
                <span className="result__next-main">
                  <span className="result__next-title">{result.next_lesson.title}</span>
                  <span className="result__next-meta">
                    {result.next_lesson.difficulty} · {result.next_lesson.estimated_minutes} min
                  </span>
                </span>
                <Icon name="arrowRight" size={16} />
              </Link>
            ) : result.next_lesson ? (
              <p className="result__empty">
                La próxima recomendación es esta misma lección: repítela para completarla.
              </p>
            ) : (
              <p className="result__empty">
                Completaste todas las lecciones de este catálogo. Puedes repasar cualquiera cuando
                quieras.
              </p>
            )}
          </div>

          <div className="result__actions">
            <button type="button" className="lesson-btn lesson-btn--primary" onClick={resetPractice}>
              Repetir lección
            </button>
            <Link className="lesson-btn" to="/lessons">
              Volver al catálogo
            </Link>
          </div>
        </section>
      ) : exercises.length === 0 ? (
        <EmptyState
          title="Esta lección todavía no tiene ejercicios"
          description="El catálogo de ejemplo no trae práctica para esta lección, así que no hay nada que responder todavía."
          action={
            <Link className="lesson-btn" to="/lessons">
              Volver al catálogo
            </Link>
          }
        />
      ) : (
        <form className="practice" onSubmit={(event) => void handleSubmit(event)}>
          <ol className="practice__list">
            {exercises.map((exercise, index) => {
              const inputId = `answer-${exercise.id}`;
              const prompt = (
                <>
                  <span className="practice__number">Ejercicio {index + 1}</span>
                  <span className="practice__question">{exercise.prompt}</span>
                </>
              );
              const answer = (value: string) =>
                setAnswers((current) => ({ ...current, [exercise.id]: value }));

              return (
                <li className="practice__item" key={exercise.id}>
                  {exercise.kind === "choice" ? (
                    // ADR-021: a radio group answers with the option's text, and the server grades
                    // it with the same comparison as a written answer. The right one is not marked.
                    <fieldset className="practice__choice">
                      <legend className="practice__prompt">{prompt}</legend>
                      {exercise.options.map((option) => (
                        <label className="practice__option" key={option}>
                          <input
                            type="radio"
                            name={inputId}
                            value={option}
                            checked={answers[exercise.id] === option}
                            onChange={() => answer(option)}
                            disabled={submitting}
                          />
                          <span className="practice__option-text">{option}</span>
                        </label>
                      ))}
                    </fieldset>
                  ) : (
                    <>
                      <label className="practice__prompt" htmlFor={inputId}>
                        {prompt}
                      </label>
                      <input
                        id={inputId}
                        className="practice__input"
                        type="text"
                        value={answers[exercise.id] ?? ""}
                        onChange={(event) => answer(event.target.value)}
                        maxLength={400}
                        autoComplete="off"
                        autoCapitalize="off"
                        autoCorrect="off"
                        spellCheck={false}
                        disabled={submitting}
                      />
                    </>
                  )}
                </li>
              );
            })}
          </ol>

          {submitError && <Notice live>{submitError}</Notice>}

          <div className="practice__actions">
            <button
              type="submit"
              className="lesson-btn lesson-btn--primary"
              disabled={submitting || !complete}
            >
              {submitting ? "Corrigiendo…" : "Comprobar respuestas"}
            </button>
            <p className="practice__hint" role="status">
              {answered} de {exercises.length} respondidos
            </p>
          </div>
        </form>
      )}
    </div>
  );
}
