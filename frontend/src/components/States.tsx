import type { ReactNode } from "react";
import "./States.css";

interface StateProps {
  title: string;
  description: string;
  action?: ReactNode;
}

export function EmptyState({ title, description, action }: StateProps) {
  return (
    <div className="state">
      <h2 className="state__title">{title}</h2>
      <p className="state__description">{description}</p>
      {action}
    </div>
  );
}

export function ErrorState({ title, description, action }: StateProps) {
  return (
    <div className="state state--error" role="alert">
      <h2 className="state__title">{title}</h2>
      <p className="state__description">{description}</p>
      {action}
    </div>
  );
}

export function LoadingState({ label = "Cargando…" }: { label?: string }) {
  return (
    <div className="state" role="status" aria-live="polite">
      <div className="state__spinner" aria-hidden="true" />
      <p className="state__description">{label}</p>
    </div>
  );
}
