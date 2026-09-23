import type { ApplicationListItem } from "@/api/contracts";
import { Tooltip } from "@/ui/Tooltip";
import { useOpenRecord } from "../hooks/useOpenRecord";
import { formatApplicationDate, formatRelativeUpdate } from "../model/applicationListPresentation";
import { ApplicationRecordActions } from "./ApplicationListItemActions";
import { ApplicationIdentity } from "./ApplicationIdentity";
import { ApplicationFitStatus, ApplicationProgress } from "./ApplicationListStatuses";
import { ApplicationRowNextAction } from "./ApplicationRowNextAction";

interface ApplicationListRowProps {
  ambiguous: boolean;
  clearing: boolean;
  item: ApplicationListItem;
  onClearNextAction: (item: ApplicationListItem) => void;
  onRequestDetails: (item: ApplicationListItem) => void;
  onRequestClose: (item: ApplicationListItem) => void;
  onRequestDelete: (item: ApplicationListItem) => void;
  onRequestUpdate: (item: ApplicationListItem) => void;
}

/* The update time with both dates on the system tooltip. Shared with the card footer. */
export const UpdatedAt = ({ item }: { item: ApplicationListItem }) => (
  <Tooltip
    label={`עודכנה ב־${formatApplicationDate(item.updated_at)} · נפתחה ב־${formatApplicationDate(item.created_at)}`}
  >
    <time dateTime={item.updated_at}>{formatRelativeUpdate(item.updated_at)}</time>
  </Tooltip>
);

export const ApplicationListRow = ({
  ambiguous,
  clearing,
  item,
  onClearNextAction,
  onRequestClose,
  onRequestDelete,
  onRequestDetails,
  onRequestUpdate,
}: ApplicationListRowProps) => {
  const open = useOpenRecord(() => onRequestDetails(item));

  return (
    <tr
      aria-label={`${item.target_role} אצל ${item.company}`}
      /* On the table the hover fill is on the cells rather than the row: the last row's
         corner cells are rounded to the card, and a row's own background would paint
         square past them.

         Below the table breakpoint the row is a grid, and a grid item's automatic
         minimum is its content: a long job title or company URL therefore held the whole
         row wider than the phone it was drawn on, and the board scrolled sideways. The
         cells are told they may shrink; the text inside them already wraps and clamps. */
      className="group relative grid cursor-pointer grid-cols-[minmax(0,1fr)_auto] gap-x-3 p-4 transition-colors hover:bg-cv-surface-muted focus-visible:bg-cv-surface-muted lg:table-row lg:border-b lg:border-cv-border lg:p-0 lg:last:border-b-0 lg:hover:bg-transparent lg:focus-visible:bg-transparent lg:hover:[&>td]:bg-cv-surface-muted lg:focus-visible:[&>td]:bg-cv-surface-muted lg:last:[&>td:first-child]:rounded-es-surface lg:last:[&>td:last-child]:rounded-ee-surface [&>td]:min-w-0"
      onClick={open.onClick}
      onKeyDown={open.onKeyDown}
      tabIndex={0}
    >
      <td className="col-start-1 px-0 pb-3 align-top lg:px-4 lg:py-4 lg:align-middle">
        <ApplicationIdentity ambiguous={ambiguous} item={item} variant="row" />
      </td>
      <td className="col-span-2 border-t border-cv-border px-0 py-3 align-top lg:border-0 lg:px-4 lg:py-4 lg:align-middle">
        <ApplicationProgress item={item} />
      </td>
      <td className="col-span-2 border-t border-cv-border px-0 py-3 align-top lg:border-0 lg:px-4 lg:py-4 lg:align-middle">
        <ApplicationRowNextAction clearing={clearing} item={item} onClearNextAction={onClearNextAction} />
      </td>
      <td className="col-start-1 row-start-4 border-t border-cv-border px-0 pt-3 align-top lg:border-0 lg:px-4 lg:py-4 lg:text-center lg:align-middle">
        <ApplicationFitStatus item={item} />
      </td>
      <td className="col-start-2 row-start-4 whitespace-nowrap border-t border-cv-border px-0 pt-3 align-top text-support text-cv-text-muted lg:border-0 lg:px-4 lg:py-4 lg:align-middle">
        <UpdatedAt item={item} />
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
