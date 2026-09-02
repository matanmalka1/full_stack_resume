import { Archive, ArrowLeft, Clock, FileCheck2, SlidersHorizontal } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { MouseEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import type { ApplicationListItem } from "../../api/contracts";
import { isTerminalOperation } from "../../api/operations";
import { Button } from "../../ui/Button";
import { StatusBadge } from "../../ui/StatusBadge";
import { cx } from "../../ui/cx";
import { type StatusTone, statusPresentation } from "../../ui/status";
import { actionDestination } from "../application/actionDestinations";
import { fitLevelIcon, fitLevelLabel, fitLevelTone, trackLabel } from "../application/analysisLabels";
import {
  actionLabel,
  preparationStateIcons,
  preparationStateLabels,
  preparationStateTones,
  recruitmentStatusIcon,
  recruitmentStatusLabel,
  recruitmentStatusTone,
} from "../application/applicationLabels";
import { operationTypeLabels, statusLabels, statusTones } from "../operationLabels";
import {
  applicationAttention,
  formatApplicationDate,
  isApplicationClosed,
  isNextActionOverdue,
  sourceHost,
} from "./applicationListPresentation";

const CompanyMark = ({ company }: { company: string }) => (
  <span
    aria-hidden="true"
    className="flex size-9 shrink-0 items-center justify-center rounded-control bg-cv-accent-soft text-support font-bold text-cv-accent"
  >
    {[...company][0] ?? "?"}
  </span>
);

/* Three tinted pills per row read as three competing headlines, so only two things in a
   row are drawn as one: what the CV needs and what is blocking it. The quieter axes -
   the analysis fit and the recruitment stage - keep the same tone vocabulary as a mark
   and a word with no chip around them, which leaves the single accent pill in "המשך
   הכנה" as the row's one call to action. A.2 still holds: tone, icon, and the Hebrew
   word travel together either way. */
const quietToneClasses: Record<StatusTone, string> = {
  success: "text-cv-success",
  warning: "text-cv-warning",
  blocker: "text-cv-blocker",
  progress: "text-cv-accent",
  neutral: "text-cv-text-muted",
};

interface QuietStatusProps {
  children: string;
  icon?: LucideIcon;
  tone: StatusTone;
}

const QuietStatus = ({ children, icon, tone }: QuietStatusProps) => {
  const Icon = icon ?? statusPresentation[tone].icon;

  return (
    <span className={cx("inline-flex items-start gap-1.5 text-support font-medium", quietToneClasses[tone])}>
      <Icon aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
      <span className="min-w-0">{children}</span>
    </span>
  );
};

/* The label wraps rather than pinning the column to its longest string: "יצירת קובץ
   קורות החיים" alone was holding roughly a tenth of the table open, which the table
   paid for with a horizontal scrollbar at laptop widths. */
/* The list packs nine columns into one row, so its badges run tighter than the
   shared default: a smaller icon gap and narrower side padding, applied here rather
   than in StatusBadge, which eight calmer screens also use. */
const rowBadgeClasses = "gap-1.5 px-2.5 text-start";

const DUPLICATE_IDENTITY_HINT = "קיימת עוד מועמדות לאותה חברה ולאותו תפקיד";

const rowRevisionLinkClasses =
  "inline-flex items-center gap-1.5 rounded-pill text-support font-semibold text-cv-accent hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cv-focus";

const rowActionClasses =
  "inline-flex min-h-9 items-center justify-center gap-2 rounded-pill bg-cv-accent-soft px-3 py-1 text-start text-support font-semibold text-cv-accent transition-colors duration-200 hover:bg-cv-accent hover:text-cv-on-accent";

/* Track and origin, on one muted line under the role: both are what the reader uses to
   tell two similar postings apart, and neither earns a column of its own. The origin is
   a link when the posting carried a URL, and the stored source name otherwise - except
   "manual", which says only that the user pasted it and is what most rows would show. */
const ProvenanceLine = ({ item }: { item: ApplicationListItem }) => {
  const host = sourceHost(item.source_url);
  const origin = host ?? (item.source === "manual" ? null : item.source);
  const parts = [item.track == null ? null : trackLabel(item.track), origin].filter((part) => part !== null);

  if (parts.length === 0) {
    return null;
  }

  return (
    <p className="truncate text-support text-cv-text-muted">
      {item.track == null ? null : trackLabel(item.track)}
      {item.track != null && origin !== null ? " · " : null}
      {origin === null ? null : host === null || item.source_url == null ? (
        origin
      ) : (
        <a
          className="hover:underline"
          dir="ltr"
          href={item.source_url}
          rel="noreferrer"
          target="_blank"
          title={item.source_url}
        >
          {host}
        </a>
      )}
    </p>
  );
};

const FitCell = ({ item }: { item: ApplicationListItem }) => {
  /* The confidence is the classifier's own certainty about the track and the fit. It is
     a qualifier on the verdict rather than a number of its own: a row is scanned for the
     verdict, and a percentage beside every one of them reads as a score the system does
     not claim to have. */
  const confidence =
    item.classification_confidence == null
      ? undefined
      : `רמת הביטחון של הסיווג: ${Math.round(item.classification_confidence * 100)}%`;

  return (
    <td className="px-3 py-3 align-top">
      {item.fit_level == null ? (
        <span className="text-support text-cv-text-muted" title="המשרה טרם נותחה">
          —
        </span>
      ) : (
        <span title={confidence}>
          <QuietStatus icon={fitLevelIcon(item.fit_level)} tone={fitLevelTone(item.fit_level)}>
            {fitLevelLabel(item.fit_level)}
          </QuietStatus>
        </span>
      )}
    </td>
  );
};

const RecruitmentStatusCell = ({ item }: { item: ApplicationListItem }) => {
  const closed = isApplicationClosed(item);

  return (
    <td className="px-3 py-3 align-top">
      <div className="flex flex-col items-start gap-1">
        <QuietStatus
          icon={recruitmentStatusIcon(item.recruitment_status)}
          tone={recruitmentStatusTone(item.recruitment_status)}
        >
          {recruitmentStatusLabel(item.recruitment_status)}
        </QuietStatus>
        {closed ? <span className="text-support text-cv-text-muted">התהליך נסגר</span> : null}
      </div>
    </td>
  );
};

const NextActionCell = ({ item }: { item: ApplicationListItem }) => {
  const overdue = isNextActionOverdue(item.next_action_date);

  return (
    <td className="px-3 py-3 align-top">
      {item.next_action == null ? (
        /* An em dash rather than "טרם נקבעה": the sentence repeated down a column of
           rows that mostly have no recruitment task, and read as content. */
        <span className="text-support text-cv-text-muted" title="לא נקבעה משימת גיוס">
          —
        </span>
      ) : (
        <div className="flex flex-col items-start gap-1">
          <span className="text-support text-cv-text" dir="auto">
            {item.next_action}
          </span>
          {item.next_action_date == null ? null : (
            <span className="flex items-center gap-1.5 text-support text-cv-text-muted">
              {overdue ? (
                <StatusBadge className="gap-1 px-2 py-0.5" tone="warning">
                  באיחור
                </StatusBadge>
              ) : null}
              <span className="inline-flex items-center gap-1.5">
                <Clock aria-hidden="true" className="size-3.5 shrink-0" />
                {formatApplicationDate(item.next_action_date)}
              </span>
            </span>
          )}
        </div>
      )}
    </td>
  );
};

const RecommendedActionContent = ({ item }: { item: ApplicationListItem }) => {
  const href = `/applications/${encodeURIComponent(item.id)}`;
  const latest = item.active_operation ?? item.latest_operation;
  /* Terminal only means that polling may stop; it does not mean the outcome is safe to
     hide. A failure remains the row's most important next-action fact until a newer run
     supersedes it. Interrupted work has the same property. Successful and deliberately
     cancelled work yield the column back to the projection's normal recommendation. */
  const reported =
    latest != null && (!isTerminalOperation(latest) || latest.status === "failed" || latest.status === "interrupted")
      ? latest
      : null;
  /* A ready revision no longer suppresses the recommendation. The projection recommends
     against the current sources, so after a posting or policy change it asks for new work
     while an older approved revision still exists; showing only the revision hid that
     from the board. The recommendation leads and the revision follows it as a second
     link, so both stay reachable from the row. */
  const readyRevisionLink =
    item.latest_ready_revision_id == null ? null : (
      <Link className={rowRevisionLinkClasses} to={`/revisions/${encodeURIComponent(item.latest_ready_revision_id)}`}>
        <FileCheck2 aria-hidden="true" className="size-3.5 shrink-0" />
        הגרסה המוכנה
      </Link>
    );

  return (
    <div className="flex flex-col items-start gap-1">
      {reported !== null ? (
        <StatusBadge className={rowBadgeClasses} tone={statusTones[reported.status]}>
          {operationTypeLabels[reported.operation_type]} · {statusLabels[reported.status]}
        </StatusBadge>
      ) : item.recommended_action != null ? (
        <Link className={rowActionClasses} to={actionDestination(item.recommended_action, item.id) ?? href}>
          <ArrowLeft aria-hidden="true" className="size-4" />
          {actionLabel(item.recommended_action)}
        </Link>
      ) : readyRevisionLink === null ? (
        <span className="text-support text-cv-text-muted">—</span>
      ) : null}
      {reported === null ? readyRevisionLink : null}
    </div>
  );
};

const QuickActionsCell = ({
  item,
  onRequestClose,
  onRequestUpdate,
}: {
  item: ApplicationListItem;
  onRequestClose: (item: ApplicationListItem) => void;
  onRequestUpdate: (item: ApplicationListItem) => void;
}) => {
  const closed = isApplicationClosed(item);

  return (
    <td className="px-3 py-3 align-top">
      <div className="flex items-start justify-between gap-1.5">
        <RecommendedActionContent item={item} />
        <div className="flex shrink-0 items-center gap-0.5">
          <button
            aria-label={`עדכון סטטוס ומשימות עבור ${item.company}`}
            className="inline-flex min-h-9 items-center rounded-control px-2 text-cv-text-muted transition-colors hover:bg-cv-surface-muted hover:text-cv-text"
            onClick={() => onRequestUpdate(item)}
            title="עדכון סטטוס ומשימות"
            type="button"
          >
            <SlidersHorizontal aria-hidden="true" className="size-4" />
          </button>
          {closed ? null : (
            <Button
              aria-label={`סגירת המועמדות ${item.company}`}
              className="min-h-9 px-2 text-cv-text-muted hover:text-cv-blocker"
              onClick={() => onRequestClose(item)}
              title="סגירת מועמדות"
              variant="ghost"
            >
              <Archive aria-hidden="true" className="size-4" />
            </Button>
          )}
        </div>
      </div>
    </td>
  );
};

interface ApplicationListRowProps {
  ambiguous: boolean;
  item: ApplicationListItem;
  onRequestClose: (item: ApplicationListItem) => void;
  onRequestUpdate: (item: ApplicationListItem) => void;
}

export const ApplicationListRow = ({ ambiguous, item, onRequestClose, onRequestUpdate }: ApplicationListRowProps) => {
  const navigate = useNavigate();
  const href = `/applications/${encodeURIComponent(item.id)}`;
  const preparationHref = `${href}/preparation`;
  const attention = applicationAttention(item);

  /* The row was already painted on hover while only three cells were clickable. It now
     navigates as a whole, and yields to whatever the reader actually aimed at: a link,
     the archive button, or a selection they were dragging over the text. The company
     link stays the keyboard and screen-reader route into the Application - a `tr` takes
     no focus, so the click handler is an addition to that route, not a replacement. */
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
        <div className="flex min-w-0 items-start gap-2">
          <CompanyMark company={item.company} />
          <div className="min-w-0 flex-1 text-left">
            <Link className="block truncate text-support font-bold text-cv-text hover:underline" dir="auto" to={href}>
              {item.company}
            </Link>
            <p className="truncate text-support text-cv-text-muted" dir="auto">
              {item.target_role}
            </p>
            <ProvenanceLine item={item} />
            {/* Two rows for the same company and role are told apart by when each was
                opened, so the hint names itself and carries that date instead of
                emphasizing a column every other row also had. */}
            {ambiguous ? (
              <p className="truncate text-support font-medium text-cv-text" title={DUPLICATE_IDENTITY_HINT}>
                {DUPLICATE_IDENTITY_HINT} · נפתחה ב־{formatApplicationDate(item.created_at)}
              </p>
            ) : null}
          </div>
        </div>
      </td>
      <RecruitmentStatusCell item={item} />
      <td className="px-3 py-3 align-top">
        <div className="flex flex-col items-start gap-1.5">
          <StatusBadge
            className={rowBadgeClasses}
            icon={preparationStateIcons[item.preparation_state]}
            tone={preparationStateTones[item.preparation_state]}
          >
            {preparationStateLabels[item.preparation_state]}
          </StatusBadge>
          {attention === null ? null : (
            /* The badge names what is waiting rather than counting it, and links to the
               preparation screen, where the alert region states each item with the control that
               resolves it. `title` and `aria-label` sit on the link because StatusBadge
               carries neither, and they hold every title - the badge itself shows at most
               two, then the most severe one and how many it stands in front of. */
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
      <FitCell item={item} />
      <NextActionCell item={item} />
      <td className="whitespace-nowrap px-3 py-3 align-top text-support text-cv-text-muted">
        <span className="inline-flex items-center gap-1.5" title={`נפתחה ב־${formatApplicationDate(item.created_at)}`}>
          <Clock aria-hidden="true" className="size-3.5 shrink-0" />
          {formatApplicationDate(item.updated_at)}
        </span>
      </td>
      <QuickActionsCell item={item} onRequestClose={onRequestClose} onRequestUpdate={onRequestUpdate} />
    </tr>
  );
};
