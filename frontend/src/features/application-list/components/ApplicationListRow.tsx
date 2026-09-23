import type { KeyboardEvent, MouseEvent } from "react";
import { useNavigate } from "react-router-dom";

import type { ApplicationListItem } from "@/api/contracts";
import { preparationResumeDestination } from "@/features/preparation";
import { formatApplicationDate, formatRelativeUpdate } from "../model/applicationListPresentation";
import { ApplicationRecordActions } from "./ApplicationListItemActions";
import { ApplicationIdentity } from "./ApplicationIdentity";
import {
  ApplicationFitStatus,
  ApplicationPreparationStatus,
  ApplicationRecruitmentStatus,
} from "./ApplicationListStatuses";
import { ApplicationRowNextAction, ApplicationRunningOperation } from "./ApplicationRowNextAction";

interface ApplicationListRowProps {
  ambiguous: boolean;
  clearing: boolean;
  item: ApplicationListItem;
  onClearNextAction: (item: ApplicationListItem) => void;
  onRequestClose: (item: ApplicationListItem) => void;
  onRequestDelete: (item: ApplicationListItem) => void;
  onRequestUpdate: (item: ApplicationListItem) => void;
}

export const ApplicationListRow = ({
  ambiguous,
  clearing,
  item,
  onClearNextAction,
  onRequestClose,
  onRequestDelete,
  onRequestUpdate,
}: ApplicationListRowProps) => {
  const navigate = useNavigate();
  const href = preparationResumeDestination(item);

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

  return (
    <tr
      aria-label={`${item.target_role} אצל ${item.company}`}
      /* Below the table breakpoint the row is a grid, and a grid item's automatic
         minimum is its content: a long job title or company URL therefore held the whole
         row wider than the phone it was drawn on, and the board scrolled sideways. The
         cells are told they may shrink; the text inside them already wraps and clamps. */
      className="group relative grid cursor-pointer grid-cols-[minmax(0,1fr)_auto] gap-x-3 p-4 transition-colors hover:bg-cv-surface-muted focus-visible:bg-cv-surface-muted lg:table-row lg:border-b lg:border-cv-border lg:p-0 lg:last:border-b-0 lg:[&>td:first-child]:ps-4 lg:[&>td:last-child]:pe-4 [&>td]:min-w-0"
      onClick={openRow}
      onKeyDown={openRowFromKeyboard}
      tabIndex={0}
    >
      <td className="col-start-1 px-0 pb-3 align-top lg:px-4 lg:py-4 lg:align-middle">
        <ApplicationIdentity ambiguous={ambiguous} item={item} variant="row" />
      </td>
      <td className="col-span-2 border-t border-cv-border px-0 py-3 align-top lg:border-0 lg:px-4 lg:py-4 lg:align-middle">
        <div className="flex flex-col items-start gap-2">
          <ApplicationPreparationStatus item={item} variant="row" />
          <div className="flex flex-wrap items-center gap-1.5">
            <ApplicationRecruitmentStatus item={item} variant="row" />
            <ApplicationRunningOperation item={item} />
          </div>
        </div>
      </td>
      <td className="col-span-2 border-t border-cv-border px-0 py-3 align-top lg:border-0 lg:px-4 lg:py-4 lg:align-middle">
        <ApplicationRowNextAction clearing={clearing} item={item} onClearNextAction={onClearNextAction} />
      </td>
      <td className="col-start-1 row-start-4 border-t border-cv-border px-0 pt-3 align-top lg:border-0 lg:px-4 lg:py-4 lg:text-center lg:align-middle">
        <ApplicationFitStatus item={item} variant="row" />
      </td>
      <td
        className="col-start-2 row-start-4 whitespace-nowrap border-t border-cv-border px-0 pt-3 align-top text-support text-cv-text-muted lg:border-0 lg:px-4 lg:py-4 lg:align-middle"
        title={`עודכנה ב־${formatApplicationDate(item.updated_at)} · נפתחה ב־${formatApplicationDate(item.created_at)}`}
      >
        <time dateTime={item.updated_at}>{formatRelativeUpdate(item.updated_at)}</time>
      </td>
      <td className="col-start-2 row-start-1 px-0 pb-3 align-top lg:px-4 lg:py-4 lg:text-center lg:align-middle">
        <ApplicationRecordActions
          item={item}
          onRequestClose={onRequestClose}
          onRequestDelete={onRequestDelete}
          onRequestUpdate={onRequestUpdate}
        />
      </td>
    </tr>
  );
};
