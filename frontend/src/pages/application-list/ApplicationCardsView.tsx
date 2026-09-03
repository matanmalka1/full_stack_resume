import { AlertTriangle, Clock } from "lucide-react";
import { Link } from "react-router-dom";

import type { ApplicationListItem } from "../../api/contracts";
import { appRoutes } from "../../app/appRoutes";
import { surfaceClasses } from "../../ui/Surface";
import { cx } from "../../ui/cx";
import { applicationAttention, formatApplicationDate } from "./applicationListPresentation";
import { ApplicationRecommendedAction, ApplicationRecordActions } from "./ApplicationListItemActions";
import { ApplicationIdentity, ApplicationNextAction, ApplicationPreparationBadge } from "./ApplicationListParts";
import { ApplicationFitStatus, ApplicationRecruitmentStatus } from "./ApplicationListStatuses";

interface ApplicationCardsViewProps {
  items: readonly ApplicationListItem[];
  onRequestClose: (item: ApplicationListItem) => void;
  onRequestUpdate: (item: ApplicationListItem) => void;
}

const ApplicationCard = ({
  item,
  onRequestClose,
  onRequestUpdate,
}: {
  item: ApplicationListItem;
  onRequestClose: ApplicationCardsViewProps["onRequestClose"];
  onRequestUpdate: ApplicationCardsViewProps["onRequestUpdate"];
}) => {
  const attention = applicationAttention(item);

  return (
    <article
      className={surfaceClasses(
        "group flex h-full flex-col bg-cv-surface-raised p-5 shadow-surface transition-all hover:border-cv-border-strong hover:shadow-floating",
      )}
    >
      <div className="flex-1">
        <div className="mb-3 flex items-start justify-between gap-3">
          <ApplicationIdentity item={item} variant="card" />
          <ApplicationFitStatus item={item} variant="card" />
        </div>

        <div className="mb-3 flex flex-wrap items-center gap-1.5">
          <ApplicationRecruitmentStatus item={item} variant="card" />
          <ApplicationPreparationBadge item={item} variant="card" />
        </div>

        <ApplicationNextAction closed={item.is_closed} item={item} variant="card" />

        {attention == null ? null : (
          <Link
            className={cx(
              "mb-3 flex items-start gap-1.5 rounded-control border px-3 py-2 text-support font-semibold hover:underline",
              attention.tone === "blocker"
                ? "border-cv-blocker/30 bg-cv-blocker-soft text-cv-blocker"
                : "border-cv-warning/30 bg-cv-warning-soft text-cv-warning",
            )}
            to={appRoutes.preparation(item.id)}
          >
            <AlertTriangle aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
            <span className="line-clamp-2">{attention.label}</span>
          </Link>
        )}

        {item.notes === "" || attention != null || item.next_action != null ? null : (
          <p className="mb-3 line-clamp-2 text-support italic text-cv-text-muted" dir="auto">
            “{item.notes}”
          </p>
        )}
      </div>

      <div className="mt-2 flex items-end justify-between gap-3 border-t border-cv-border pt-3">
        <div className="flex items-center gap-1">
          <ApplicationRecordActions item={item} onRequestClose={onRequestClose} onRequestUpdate={onRequestUpdate} />
          <span className="ms-1 inline-flex items-center gap-1 text-support text-cv-text-muted">
            <Clock aria-hidden="true" className="size-3.5" />
            {formatApplicationDate(item.updated_at)}
          </span>
        </div>
        <ApplicationRecommendedAction item={item} variant="card" />
      </div>
    </article>
  );
};

export const ApplicationCardsView = ({ items, onRequestClose, onRequestUpdate }: ApplicationCardsViewProps) => (
  <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
    {items.map((item) => (
      <ApplicationCard item={item} key={item.id} onRequestClose={onRequestClose} onRequestUpdate={onRequestUpdate} />
    ))}
  </div>
);
