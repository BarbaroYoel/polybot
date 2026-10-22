import type { ReactNode } from "react";
import "./Notice.css";

interface NoticeProps {
  children: ReactNode;
  /** Adds a live region. Use it only for feedback that appears after a user action. */
  live?: boolean;
}

/**
 * Shared inline notice (example data, prototype feedback). It is a normal
 * flow element: it never floats over the content next to it.
 */
export function Notice({ children, live = false }: NoticeProps) {
  const liveProps = live ? { role: "status" as const, "aria-live": "polite" as const } : {};

  return (
    <p className="notice" {...liveProps}>
      {children}
    </p>
  );
}
