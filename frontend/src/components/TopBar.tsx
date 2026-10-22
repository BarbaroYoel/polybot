import { useActiveLanguage } from "../lib/language";
import { Icon } from "./Icon";
import "./TopBar.css";

interface TopBarProps {
  onOpenMenu: () => void;
}

export function TopBar({ onOpenMenu }: TopBarProps) {
  const { active, status } = useActiveLanguage();

  // The language badge waits for the API: no invented name and no invented level (F2 S9).
  const contextName =
    active?.name ?? (status === "loading" ? "Cargando idioma…" : "Sin idioma activo");

  return (
    <header className="topbar">
      <button type="button" className="topbar__menu" onClick={onOpenMenu} aria-label="Abrir menú de navegación">
        <Icon name="menu" />
      </button>

      <div className="topbar__greeting">
        <h1 className="topbar__title">Hola, ¡sigamos aprendiendo!</h1>
        <p className="topbar__subtitle">Practica, conversa y mejora cada día</p>
      </div>

      <p className="topbar__context" aria-label="Idioma activo">
        <Icon name="globe" size={16} />
        <span className="topbar__context-name">{contextName}</span>
        {active && (
          <span className="topbar__level" title="Nivel actual (solo lectura)">
            {active.level}
          </span>
        )}
      </p>

      <div className="topbar__actions">
        <button type="button" className="topbar__action" disabled title="La búsqueda todavía no está implementada" aria-label="Buscar">
          <Icon name="search" />
        </button>
        <button type="button" className="topbar__action" disabled title="El perfil de usuario está pendiente de decisión (Q5)" aria-label="Perfil">
          <Icon name="user" />
        </button>
      </div>
    </header>
  );
}
