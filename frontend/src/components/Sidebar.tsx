import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { Icon } from "./Icon";
import type { IconName } from "./Icon";
import { Notice } from "./Notice";
import { errorMessage } from "../lib/api/client";
import { useActiveLanguage } from "../lib/language";
import "./Sidebar.css";

interface NavItem {
  to: string;
  label: string;
  icon: IconName;
  /** Extra routes that keep this item active (ADR-011). */
  alsoActiveOn?: string[];
}

const PRIMARY_NAV: NavItem[] = [
  // Home and an open conversation are the same section (ADR-011).
  { to: "/", label: "Conversaciones", icon: "chat", alsoActiveOn: ["/chat"] },
  { to: "/lessons", label: "Lecciones", icon: "book" },
  { to: "/plans", label: "Planes de estudio", icon: "calendar" },
  { to: "/translate", label: "Traducción en tiempo real", icon: "translate" },
  { to: "/progress", label: "Progreso", icon: "progress" },
];

function isItemActive(item: NavItem, pathname: string): boolean {
  if (pathname === item.to) return true;
  if (pathname.startsWith(`${item.to}/`)) return true;
  return Boolean(item.alsoActiveOn?.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`)));
}

interface SidebarProps {
  open: boolean;
  onClose: () => void;
}

export function Sidebar({ open, onClose }: SidebarProps) {
  const { languages, active, status, error, setActiveCode } = useActiveLanguage();
  const { pathname } = useLocation();
  const [pendingCode, setPendingCode] = useState<string | null>(null);
  const [activationError, setActivationError] = useState<string | null>(null);

  const activate = async (code: string) => {
    // One activation at a time: the second response could otherwise overwrite the first.
    if (pendingCode) return;
    setPendingCode(code);
    setActivationError(null);
    try {
      await setActiveCode(code);
    } catch (error: unknown) {
      setActivationError(errorMessage(error));
    } finally {
      setPendingCode(null);
    }
  };

  return (
    <nav className={`sidebar${open ? " sidebar--open" : ""}`} aria-label="Navegación principal">
      <div className="sidebar__brand">
        <span className="sidebar__brand-mark" aria-hidden="true">
          <Icon name="chat" size={18} />
        </span>
        <span className="sidebar__brand-text">Tutor de Idiomas</span>
        <button type="button" className="sidebar__close" onClick={onClose} aria-label="Cerrar menú">
          <Icon name="close" />
        </button>
      </div>

      <ul className="sidebar__nav">
        {PRIMARY_NAV.map((item) => {
          const isActive = isItemActive(item, pathname);
          return (
            <li key={item.to}>
              <Link
                to={item.to}
                className={`sidebar__link${isActive ? " sidebar__link--active" : ""}`}
                aria-current={isActive ? "page" : undefined}
              >
                <Icon name={item.icon} />
                <span>{item.label}</span>
              </Link>
            </li>
          );
        })}
      </ul>

      <div className="sidebar__section">
        <div className="sidebar__section-head">
          <span>Mis idiomas</span>
          <Link className="sidebar__add" to="/languages" title="Agregar idioma" aria-label="Agregar idioma">
            <Icon name="plus" size={18} />
          </Link>
        </div>

        {languages.length > 0 && (
          <ul className="sidebar__languages">
            {languages.map((language) => {
              // The active language comes from the server (`is_active`), not from a local choice.
              const isActive = language.id === active?.id;
              return (
                <li key={language.id}>
                  <button
                    type="button"
                    className={`sidebar__language${isActive ? " sidebar__language--active" : ""}`}
                    aria-pressed={isActive}
                    aria-busy={pendingCode === language.code}
                    onClick={() => void activate(language.code)}
                  >
                    <Icon name="globe" size={18} />
                    <span className="sidebar__language-name">{language.name}</span>
                    {/* Nivel como dato de solo lectura (ADR-008): no es un selector. */}
                    <span className="sidebar__level" title={`Nivel actual: ${language.level}`}>
                      {language.level}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        )}

        {languages.length === 0 && status !== "error" && (
          <Notice live={status === "loading"}>
            {status === "loading"
              ? "Cargando tus idiomas…"
              : "Todavía no hay idiomas en tu lista. Agrega uno desde Mis idiomas."}
          </Notice>
        )}

        {status === "error" && error && <Notice live>{errorMessage(error)}</Notice>}
        {activationError && <Notice live>{activationError}</Notice>}
      </div>

      <div className="sidebar__footer">
        <Link
          to="/settings"
          className={`sidebar__link${pathname === "/settings" ? " sidebar__link--active" : ""}`}
          aria-current={pathname === "/settings" ? "page" : undefined}
        >
          <Icon name="settings" />
          <span>Configuración</span>
        </Link>
      </div>
    </nav>
  );
}
