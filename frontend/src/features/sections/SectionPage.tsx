import type { ReactNode } from "react";
import "./SectionPage.css";

interface SectionPageProps {
  title: string;
  description: string;
  phase: string;
  items: string[];
  children?: ReactNode;
}

/**
 * Vista base de una sección de F1: título, propósito y lo que va a vivir acá.
 * No inventa contenido de producto que todavía no existe (desing.md §14).
 */
export function SectionPage({ title, description, phase, items, children }: SectionPageProps) {
  return (
    <div className="page">
      <header className="page__head">
        <div>
          <h1 className="page__title">{title}</h1>
          <p className="page__description">{description}</p>
        </div>
        <span className="page__phase" title="Estado de esta vista">
          {phase}
        </span>
      </header>

      {children}

      <section className="page__card">
        <h2 className="page__card-title">Qué va a incluir</h2>
        <ul className="page__list">
          {items.map((item) => (
            <li key={item} className="page__list-item">
              {item}
            </li>
          ))}
        </ul>
        <p className="page__hint">
          Vista base de F1: estructura y navegación reales, contenido todavía de ejemplo.
        </p>
      </section>
    </div>
  );
}
