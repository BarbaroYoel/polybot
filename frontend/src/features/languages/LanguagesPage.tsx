import { useState } from "react";
import type { FormEvent } from "react";
import { Icon } from "../../components/Icon";
import { Notice } from "../../components/Notice";
import { EmptyState, ErrorState, LoadingState } from "../../components/States";
import { errorMessage } from "../../lib/api/client";
import { archiveLanguage, createLanguage, updateLanguage } from "../../lib/api/languages";
import type { CefrLevel, LanguageProfile } from "../../lib/api/types";
import { useActiveLanguage } from "../../lib/language";
import "../sections/SectionPage.css";
import "./languages.css";

const LEVELS: CefrLevel[] = ["A1", "A2", "B1", "B2", "C1", "C2"];

const EMPTY_FORM = { code: "", name: "", level: "A1" as CefrLevel };

interface RowError {
  id: string;
  message: string;
}

/**
 * `/languages` (desing.md §6.6). Every control here has a real effect on the API: activate
 * (`PATCH is_active`), change level (`PATCH level`, an explicit action per ADR-008), archive
 * (`DELETE`, confirmed first) and add (`POST`). The level never behaves as a filter.
 */
export function LanguagesPage() {
  const { status, languages, active, error, setActiveCode, reload } = useActiveLanguage();

  const [pendingId, setPendingId] = useState<string | null>(null);
  const [rowError, setRowError] = useState<RowError | null>(null);
  const [confirmingId, setConfirmingId] = useState<string | null>(null);
  const [editingLevelId, setEditingLevelId] = useState<string | null>(null);
  const [levelDraft, setLevelDraft] = useState<CefrLevel>("A1");

  const [form, setForm] = useState(EMPTY_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [formNotice, setFormNotice] = useState<string | null>(null);

  const busy = pendingId !== null;

  const activate = async (language: LanguageProfile) => {
    setPendingId(language.id);
    setRowError(null);
    try {
      await setActiveCode(language.code);
    } catch (error: unknown) {
      setRowError({ id: language.id, message: errorMessage(error) });
    } finally {
      setPendingId(null);
    }
  };

  const openLevelEditor = (language: LanguageProfile) => {
    setConfirmingId(null);
    setRowError(null);
    setEditingLevelId(language.id);
    setLevelDraft(language.level);
  };

  const saveLevel = async (language: LanguageProfile) => {
    if (levelDraft === language.level) {
      setEditingLevelId(null);
      return;
    }

    setPendingId(language.id);
    setRowError(null);
    try {
      await updateLanguage(language.id, { level: levelDraft });
      setEditingLevelId(null);
      // The level is part of the shell's context badge: refresh it from the server.
      reload();
    } catch (error: unknown) {
      setRowError({ id: language.id, message: errorMessage(error) });
    } finally {
      setPendingId(null);
    }
  };

  const confirmArchive = async (language: LanguageProfile) => {
    setPendingId(language.id);
    setRowError(null);
    try {
      await archiveLanguage(language.id);
      setConfirmingId(null);
      reload();
    } catch (error: unknown) {
      // 409 from the API: archiving the active language (or the last one) has an actionable message.
      setRowError({ id: language.id, message: errorMessage(error) });
    } finally {
      setPendingId(null);
    }
  };

  const addLanguage = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (submitting) return;

    setSubmitting(true);
    setFormError(null);
    setFormNotice(null);
    try {
      const created = await createLanguage({
        code: form.code.trim(),
        name: form.name.trim(),
        level: form.level,
      });
      setForm(EMPTY_FORM);
      setFormNotice(`Agregamos ${created.name}. Actívalo cuando quieras usarlo.`);
      reload();
    } catch (error: unknown) {
      // 409 (repeated code) and 422 (invalid data) both arrive with a Spanish message.
      setFormError(errorMessage(error));
    } finally {
      setSubmitting(false);
    }
  };

  const canSubmit = form.code.trim().length >= 2 && form.name.trim().length > 0 && !submitting;

  const renderLanguages = () => {
    if (status === "loading" && languages.length === 0) {
      return <LoadingState label="Cargando tus idiomas…" />;
    }

    if (status === "error" && languages.length === 0) {
      return (
        <ErrorState
          title="No pudimos cargar tus idiomas"
          description={errorMessage(error)}
          action={
            <button type="button" className="language-action" onClick={reload}>
              Reintentar
            </button>
          }
        />
      );
    }

    if (languages.length === 0) {
      return (
        <EmptyState
          title="Todavía no agregaste idiomas"
          description="Usa el formulario de abajo para agregar el primero. Después puedes activarlo y empezar a conversar."
        />
      );
    }

    return (
      <>
        {status === "error" && (
          <>
            <Notice live>{errorMessage(error)}</Notice>
            <div className="languages__actions">
              <button type="button" className="language-action" onClick={reload}>
                Reintentar
              </button>
            </div>
          </>
        )}

        <ul className="languages__list">
        {languages.map((language) => {
          const isActive = language.id === active?.id;
          const isPending = pendingId === language.id;
          const isEditingLevel = editingLevelId === language.id;
          const isConfirmingArchive = confirmingId === language.id;

          return (
            <li className="language-row" key={language.id}>
              <span className="language-row__icon" aria-hidden="true">
                <Icon name="globe" size={18} />
              </span>

              <div className="language-row__main">
                <p className="language-row__title">
                  {language.name}
                  <span className="language-row__code">{language.code}</span>
                  {isActive && <span className="language-row__badge">Activo</span>}
                </p>
                <p className="language-row__meta">
                  Nivel {language.level} · Explicaciones en «{language.explanation_language}»
                </p>

                {isActive && (
                  <p className="language-row__note">
                    Es el idioma de Inicio, Lecciones, Planes y Progreso.
                  </p>
                )}

                {rowError?.id === language.id && <Notice live>{rowError.message}</Notice>}

                {isEditingLevel && (
                  <div className="language-level">
                    <label className="language-level__label" htmlFor={`level-${language.id}`}>
                      Nuevo nivel para {language.name}
                    </label>
                    <select
                      id={`level-${language.id}`}
                      className="language-level__select"
                      value={levelDraft}
                      onChange={(event) => setLevelDraft(event.target.value as CefrLevel)}
                    >
                      {LEVELS.map((level) => (
                        <option key={level} value={level}>
                          {level}
                        </option>
                      ))}
                    </select>
                    <button
                      type="button"
                      className="language-action language-action--primary"
                      onClick={() => void saveLevel(language)}
                      disabled={busy || levelDraft === language.level}
                    >
                      {isPending ? "Guardando…" : "Guardar nivel"}
                    </button>
                    <button
                      type="button"
                      className="language-action"
                      onClick={() => setEditingLevelId(null)}
                      disabled={isPending}
                    >
                      Cancelar
                    </button>
                    <p className="language-row__note">
                      Cambiar el nivel actualiza el contexto de este idioma; los demás no se tocan.
                    </p>
                  </div>
                )}

                {isConfirmingArchive && (
                  <div className="language-confirm" role="group" aria-label={`Confirmar archivo de ${language.name}`}>
                    <p className="language-confirm__text">
                      ¿Archivar {language.name}? Deja de aparecer en la navegación; su historial no
                      se borra.
                    </p>
                    <button
                      type="button"
                      className="language-action language-action--primary"
                      onClick={() => void confirmArchive(language)}
                      disabled={isPending}
                    >
                      {isPending ? "Archivando…" : "Sí, archivar"}
                    </button>
                    <button
                      type="button"
                      className="language-action"
                      onClick={() => setConfirmingId(null)}
                      disabled={isPending}
                    >
                      Cancelar
                    </button>
                  </div>
                )}
              </div>

              <div className="language-row__actions">
                {!isActive && (
                  <button
                    type="button"
                    className="language-action"
                    onClick={() => void activate(language)}
                    disabled={busy}
                  >
                    {isPending && !isEditingLevel && !isConfirmingArchive ? "Activando…" : "Activar"}
                  </button>
                )}
                <button
                  type="button"
                  className="language-action"
                  onClick={() => openLevelEditor(language)}
                  aria-expanded={isEditingLevel}
                  disabled={busy}
                >
                  Cambiar nivel
                </button>
                <button
                  type="button"
                  className="language-action"
                  onClick={() => {
                    setRowError(null);
                    setEditingLevelId(null);
                    setConfirmingId(language.id);
                  }}
                  aria-expanded={isConfirmingArchive}
                  disabled={busy}
                >
                  Archivar
                </button>
              </div>
            </li>
          );
        })}
      </ul>
      </>
    );
  };

  return (
    <div className="page">
      <header className="page__head">
        <div>
          <h1 className="page__title">Mis idiomas</h1>
          <p className="page__description">
            Cada idioma tiene su propio nivel, historial, lecciones y progreso. Solo uno está
            activo a la vez.
          </p>
        </div>
        <span className="page__phase" title="Origen de los datos de esta pantalla">
          Datos reales · F2
        </span>
      </header>

      {renderLanguages()}

      <form className="language-form" onSubmit={addLanguage} noValidate>
        <h2 className="language-form__title">Agregar idioma</h2>

        <div className="language-form__fields">
          <label className="language-form__field">
            <span>Código</span>
            <input
              className="language-form__input"
              name="code"
              value={form.code}
              onChange={(event) => setForm((current) => ({ ...current, code: event.target.value }))}
              placeholder="pt"
              autoComplete="off"
              maxLength={8}
              required
            />
          </label>

          <label className="language-form__field">
            <span>Nombre</span>
            <input
              className="language-form__input"
              name="name"
              value={form.name}
              onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
              placeholder="Portugués"
              autoComplete="off"
              maxLength={80}
              required
            />
          </label>

          <label className="language-form__field">
            <span>Nivel inicial</span>
            <select
              className="language-form__select"
              name="level"
              value={form.level}
              onChange={(event) =>
                setForm((current) => ({ ...current, level: event.target.value as CefrLevel }))
              }
            >
              {LEVELS.map((level) => (
                <option key={level} value={level}>
                  {level}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="language-form__actions">
          <button
            type="submit"
            className="language-action language-action--primary"
            disabled={!canSubmit}
          >
            {submitting ? "Agregando…" : "Agregar idioma"}
          </button>
        </div>

        {formError && <Notice live>{formError}</Notice>}
        {formNotice && <Notice live>{formNotice}</Notice>}

        <p className="language-form__hint">
          Código de 2 a 3 letras, por ejemplo «pt». El idioma nuevo queda inactivo hasta que lo
          actives, y el idioma de las explicaciones es «es» por ahora.
        </p>
      </form>
    </div>
  );
}
