import { Clock, TriangleAlert } from "lucide-react";
import type { KeyboardEvent, MouseEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import type { ApplicationListItem } from "@/api/contracts";
import { preparationResumeDestination } from "@/features/preparation";
import { cx } from "@/ui/cx";
import { applicationAttention, formatApplicationDate } from "../model/applicationListPresentation";
import { ApplicationRecommendedAction, ApplicationRecordActions } from "./ApplicationListItemActions";
import { ApplicationIdentity } from "./ApplicationIdentity";
import { ApplicationNextAction } from "./ApplicationNextAction";
import {
  ApplicationFitStatus,
  ApplicationPreparationStatus,
  ApplicationRecruitmentStatus,
} from "./ApplicationListStatuses";

interface ApplicationListRowProps {
  ambiguous: boolean;
  item: ApplicationListItem;
  onRequestClose: (item: ApplicationListItem) => void;
  onRequestUpdate: (item: ApplicationListItem) => void;
}

export const ApplicationListRow = ({ ambiguous, item, onRequestClose, onRequestUpdate }: ApplicationListRowProps) => {
  const navigate = useNavigate();
  const href = preparationResumeDestination(item);
  const attention = applicationAttention(item);

  /* The row navigates as a whole but yields to real controls and text selection. The
     job-title link remains the native keyboard and screen-reader route into it. */
  const openRow = (event: MouseEvent<HTMLElement>) => {
    if (event.defaultPrevented || event.target instanceof Element === false) {
      return;
    }

    /* The row looks and behaves like a link, so it yields to the gestures that open a
       link somewhere else. Without this, Cmd- or Ctrl-clicking the row body navigated in
       place - the one thing the reader was asking it not to do - while the same gesture
       on the title inside it opened a tab, because that is a real anchor. */
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button !== 0) {
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

  const openRowFromKeyboard = (event: KeyboardEvent<HTMLElement>) => {
    if ((event.key === "Enter" || event.key === " ") && event.target === event.currentTarget) {
      event.preventDefault();
      navigate(href);
    }
  };

  const attentionLink =
    attention === null ? null : (
      <Link
        aria-label={`${item.company}: ${attention.items.map((entry) => entry.title).join(" · ")}`}
        className={cx(
          "inline-flex max-w-full items-start gap-1.5 rounded-control text-support font-medium hover:underline",
          attention.tone === "blocker" ? "text-cv-blocker" : "text-cv-warning",
        )}
        title={attention.items.map((entry) => entry.title).join(" · ")}
        to={href}
      >
        <TriangleAlert aria-hidden="true" className="mt-0.5 size-icon-sm shrink-0" />
        <span className="min-w-0 line-clamp-2 lg:line-clamp-1">{attention.label}</span>
      </Link>
    );

  return (
    <tr
      aria-label={`${item.target_role} אצל ${item.company}`}
      className="group relative grid cursor-pointer grid-cols-[1fr_auto] gap-x-3 p-4 transition-colors hover:bg-cv-surface-muted focus-visible:bg-cv-surface-muted lg:table-row lg:border-b lg:border-cv-border lg:p-0 lg:last:border-b-0 lg:[&>td:first-child]:ps-4 lg:[&>td:last-child]:pe-4"
      onClick={openRow}
      onKeyDown={openRowFromKeyboard}
      tabIndex={0}
    >
      <td className="col-start-1 px-0 pb-3 align-top lg:px-3 lg:py-3">
        <ApplicationIdentity ambiguous={ambiguous} item={item} variant="row" />
      </td>
      <td className="col-span-2 border-t border-cv-border px-0 py-3 align-top lg:border-0 lg:px-3">
        <div className="flex flex-wrap items-start gap-x-4 gap-y-2 lg:flex-col">
          <ApplicationRecruitmentStatus item={item} variant="row" />
          <ApplicationFitStatus item={item} variant="row" />
        </div>
      </td>
      <td className="col-span-2 px-0 pb-3 align-top lg:px-3 lg:py-3">
        <div className="flex flex-col items-start gap-1.5">
          <ApplicationPreparationStatus item={item} variant="row" />
          {attentionLink}
        </div>
      </td>
      <td className="col-span-2 border-t border-cv-border px-0 pt-3 align-top lg:border-0 lg:px-3 lg:py-3">
        <div className="flex flex-col items-start gap-2">
          <ApplicationNextAction item={item} variant="row" />
          <ApplicationRecommendedAction item={item} variant="row" />
        </div>
      </td>
      <td className="col-start-2 row-start-5 whitespace-nowrap px-0 pt-3 align-bottom text-support text-cv-text-muted lg:px-3 lg:py-3 lg:align-top">
        <span className="inline-flex items-center gap-1.5" title={`נפתחה ב־${formatApplicationDate(item.created_at)}`}>
          <Clock aria-hidden="true" className="size-icon-sm shrink-0" />
          {formatApplicationDate(item.updated_at)}
        </span>
      </td>
      <td className="col-start-2 row-start-1 px-0 pb-3 align-top lg:px-3 lg:py-3">
        <ApplicationRecordActions item={item} onRequestClose={onRequestClose} onRequestUpdate={onRequestUpdate} />
      </td>
    </tr>
  );
};
