import { Icon } from "../../components/Icon";
import type { LessonStatus, LessonUnitKind } from "../../lib/api/types";

const UNIT_KIND_LABELS: Record<LessonUnitKind, string> = {
  vocabulary: "Vocabulario",
  grammar: "Gramática",
  pronunciation: "Pronunciación",
  listening: "Escucha",
  situational: "Práctica situacional",
};

const STATUS_LABELS: Record<LessonStatus, string> = {
  pending: "Pendiente",
  in_progress: "En curso",
  completed: "Completada",
};

export function unitKindLabel(kind: LessonUnitKind): string {
  return UNIT_KIND_LABELS[kind];
}

/**
 * The state is the one the API derived from the real attempts (F5 S5): the badge only shows it,
 * and the text says it out loud, so the state never depends on color alone (desing.md §11).
 */
export function LessonStatusBadge({ status }: { status: LessonStatus }) {
  return (
    <span className={`lesson-badge lesson-badge--${status}`}>
      {status === "completed" && <Icon name="check" size={13} />}
      {STATUS_LABELS[status]}
    </span>
  );
}
