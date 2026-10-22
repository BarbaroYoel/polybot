import { Icon } from "./Icon";
import type { IconName } from "./Icon";
import "./SummaryCard.css";

interface SummaryCardProps {
  icon: IconName;
  title: string;
  meta: string;
  progress?: { current: number; total: number };
  dots?: { current: number; total: number };
  actionLabel?: string;
  onAction?: () => void;
  actionTitle?: string;
}

export function SummaryCard({
  icon,
  title,
  meta,
  progress,
  dots,
  actionLabel,
  onAction,
  actionTitle,
}: SummaryCardProps) {
  const interactive = Boolean(actionLabel && onAction);

  return (
    <section className="summary">
      <span className="summary__icon" aria-hidden="true">
        <Icon name={icon} size={18} />
      </span>

      <div className="summary__body">
        <h2 className="summary__title">{title}</h2>
        <p className="summary__meta">{meta}</p>

        {progress && (
          <div
            className="summary__bar"
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={progress.total}
            aria-valuenow={progress.current}
            aria-label={`${title}: ${progress.current} de ${progress.total}`}
          >
            <span
              className="summary__bar-fill"
              style={{ width: `${Math.min(100, (progress.current / progress.total) * 100)}%` }}
            />
          </div>
        )}

        {dots && (
          <div className="summary__dots" aria-hidden="true">
            {Array.from({ length: dots.total }, (_, index) => (
              <span
                key={index}
                className={`summary__dot${index < dots.current ? " summary__dot--on" : ""}`}
              />
            ))}
          </div>
        )}

        {actionLabel && (
          <button
            type="button"
            className="summary__action"
            onClick={onAction}
            disabled={!interactive}
            title={actionTitle}
          >
            {actionLabel}
            <Icon name="arrowRight" size={14} />
          </button>
        )}
      </div>
    </section>
  );
}
