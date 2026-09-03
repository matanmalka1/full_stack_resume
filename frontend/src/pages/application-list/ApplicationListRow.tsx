import { Clock } from "lucide-react";
import type { MouseEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import type { ApplicationListItem } from "../../api/contracts";
import { appRoutes } from "../../app/appRoutes";
import { StatusBadge } from "../../ui/StatusBadge";
import { cx } from "../../ui/cx";
import { applicationAttention, formatApplicationDate } from "./applicationListPresentation";
import { ApplicationRecommendedAction, ApplicationRecordActions } from "./ApplicationListItemActions";
import { ApplicationIdentity, ApplicationNextAction, ApplicationPreparationBadge } from "./ApplicationListParts";
import { ApplicationFitStatus, ApplicationRecruitmentStatus } from "./ApplicationListStatuses";

/* The list packs its statuses tighter than the calmer screens that use StatusBadge. */
const rowBadgeClasses = "gap-1.5 px-2.5 text-start";

interface ApplicationListRowProps {
  ambiguous: boolean;
  item: ApplicationListItem;
  onRequestClose: (item: ApplicationListItem) => void;
  onRequestUpdate: (item: ApplicationListItem) => void;
}

export const ApplicationListRow = ({ ambiguous, item, onRequestClose, onRequestUpdate }: ApplicationListRowProps) => {
  const navigate = useNavigate();
  const href = appRoutes.application(item.id);
  const preparationHref = appRoutes.preparation(item.id);
  const attention = applicationAttention(item);

  /* The row navigates as a whole but yields to real controls and text selection. The
     company link remains the keyboard and screen-reader route into the Application. */
  const openRow = (event: MouseEvent<HTMLTableRowElement>) => {
    if (event.defaultPrevented || event.target instanceof Element === false) {
      return;
    }

    if (event.target.closest("a, button, input, label") !== null) {
      return;
    }

    if ((window.getSelection()?.toString() ?? "") !== "") {
      return;
    }

    navigate(href);
  };

  return (
    <tr
      className="cursor-pointer border-b border-cv-border last:border-b-0 hover:bg-cv-surface-muted [&>td:first-child]:ps-4 [&>td:last-child]:pe-4"
      onClick={openRow}
    >
      <td className="px-3 py-3 align-top">
        <ApplicationIdentity ambiguous={ambiguous} item={item} variant="row" />
      </td>
      <td className="px-3 py-3 align-top">
        <ApplicationRecruitmentStatus item={item} variant="row" />
      </td>
      <td className="px-3 py-3 align-top">
        <div className="flex flex-col items-start gap-1.5">
          <ApplicationPreparationBadge item={item} variant="row" />
          {attention === null ? null : (
            <Link
              aria-label={`${item.company}: ${attention.items.map((entry) => entry.title).join(" · ")}`}
              className="inline-flex max-w-full rounded-pill focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cv-focus"
              title={attention.items.map((entry) => entry.title).join(" · ")}
              to={preparationHref}
            >
              <StatusBadge
                className={cx(rowBadgeClasses, "max-w-full items-start [overflow-wrap:break-word]")}
                tone={attention.tone}
              >
                <span className="min-w-0">{attention.label}</span>
              </StatusBadge>
            </Link>
          )}
        </div>
      </td>
      <td className="px-3 py-3 align-top">
        <ApplicationFitStatus item={item} variant="row" />
      </td>
      <td className="px-3 py-3 align-top">
        <ApplicationNextAction item={item} variant="row" />
      </td>
      <td className="whitespace-nowrap px-3 py-3 align-top text-support text-cv-text-muted">
        <span className="inline-flex items-center gap-1.5" title={`נפתחה ב־${formatApplicationDate(item.created_at)}`}>
          <Clock aria-hidden="true" className="size-3.5 shrink-0" />
          {formatApplicationDate(item.updated_at)}
        </span>
      </td>
      <td className="px-3 py-3 align-top">
        <div className="flex items-start justify-between gap-1.5">
          <ApplicationRecommendedAction item={item} variant="row" />
          <ApplicationRecordActions item={item} onRequestClose={onRequestClose} onRequestUpdate={onRequestUpdate} />
        </div>
      </td>
    </tr>
  );
};
