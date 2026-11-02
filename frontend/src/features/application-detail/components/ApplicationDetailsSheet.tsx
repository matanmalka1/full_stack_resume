import { ChevronLeft } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import type { PreparationState } from "@/api/contracts";
import { actionLabel, preparationStateLabels } from "@/features/preparation";
import { recruitmentStatusLabel } from "@/features/recruitment";
import { buttonClasses } from "@/ui/Button";
import { Dialog } from "@/ui/Dialog";
import { InitialTile } from "@/ui/InitialTile";
import { formatDate } from "@/utils/formatDateTime";
import { fitText } from "./ApplicationFacts";

/* What the sheet reads, in the fields the board's list item and the hub's projection
   both carry - so either screen opens the same sheet over its own record. */
interface ApplicationDetailsSummary {
  closed: boolean;
  company: string;
  fit_level?: string | null;
  next_action?: string | null;
  next_action_date?: string | null;
  notes: string;
  preparation_state: PreparationState;
  recommended_action?: string | null;
  recruitment_status: string;
  target_role: string;
}

interface ApplicationDetailsSheetProps {
  application: ApplicationDetailsSummary | null;
  /* The one way onward, as the opening screen words it: the hub continues the CV work,
     the board might open the hub itself. */
  continueTo: { label: string; to: string } | null;
  /* The opening screen's own word for what comes next, when it knows more than the
     summary does - the board knows about a run in flight or a failed one. */
  nextStep?: string | null;
  onClose: () => void;
}

const Fact = ({ label, children }: { label: string; children: ReactNode }) => (
  <div className="flex min-w-0 flex-col gap-1 rounded-control border border-cv-hairline bg-cv-canvas px-3.5 py-3">
    <dt className="text-support text-cv-text-muted">{label}</dt>
    <dd className="m-0 text-body font-bold text-cv-text">{children}</dd>
  </div>
);

const Block = ({ label, children }: { label: string; children: ReactNode }) => (
  <section aria-label={label} className="rounded-surface border border-cv-hairline px-4 py-3.5">
    <p className="mb-1.5 text-support font-bold text-cv-text-muted">{label}</p>
    {children}
  </section>
);

/* One Application at a glance: who, its four states as tiles, the one thing to do next,
   the reader's notes, and the way onward. It is a summary - every fact here is a fact the
   record's own screens show and change - so it carries one command, not the record's
   menu.

   The next thing to do is the reader's own reminder when there is one, since it is the
   reader's word about this record; otherwise the step the preparation recommends. */
export const ApplicationDetailsSheet = ({
  application,
  continueTo,
  nextStep: givenNextStep,
  onClose,
}: ApplicationDetailsSheetProps) => {
  if (application === null) return null;

  const reminder = application.next_action?.trim() ?? "";
  const nextStep =
    givenNextStep !== undefined
      ? givenNextStep
      : reminder !== ""
        ? `${reminder}${application.next_action_date == null ? "" : ` · ${formatDate(application.next_action_date)}`}`
        : application.recommended_action == null
          ? null
          : actionLabel(application.recommended_action);

  return (
    <Dialog
      footer={
        continueTo === null ? undefined : (
          <Link className={buttonClasses("primary", "w-full", "large")} onClick={onClose} to={continueTo.to}>
            {continueTo.label}
            <ChevronLeft aria-hidden="true" className="size-icon-md" />
          </Link>
        )
      }
      headingId="application-details-heading"
      onClose={onClose}
      open
      title={
        <span className="flex items-center gap-3.5">
          <InitialTile name={application.company} />
          <span className="flex min-w-0 flex-col">
            <span className="text-caption font-bold text-cv-text-muted">
              פרטי משרה<span className="sr-only">:</span>
            </span>{" "}
            <span className="truncate" dir="auto">
              {application.target_role}
            </span>{" "}
            <span className="truncate text-label font-normal text-cv-text-muted" dir="auto">
              {application.company}
            </span>
          </span>
        </span>
      }
    >
      <div className="flex flex-col gap-4">
        <dl className="m-0 grid grid-cols-2 gap-2.5">
          <Fact label="שלב גיוס">{recruitmentStatusLabel(application.recruitment_status)}</Fact>
          <Fact label="סטטוס משרה">{application.closed ? "סגורה" : "פתוחה"}</Fact>
          <Fact label="הכנת קו״ח">{preparationStateLabels[application.preparation_state]}</Fact>
          <Fact label="ציון התאמה">{fitText(application.fit_level)}</Fact>
        </dl>

        {/* Said rather than left out when nothing is scheduled or recommended: the reader
            then knows the record is waiting on them, not missing a block. */}
        <Block label="פעולה מומלצת הבאה">
          {nextStep === null ? (
            <p className="text-body text-cv-text-muted">אין פעולה מתוזמנת כעת</p>
          ) : (
            <p className="text-heading-card font-bold text-cv-text" dir="auto">
              {nextStep}
            </p>
          )}
        </Block>

        {application.notes.trim() === "" ? null : (
          <Block label="הערות">
            <p className="text-body leading-relaxed whitespace-pre-wrap text-cv-text" dir="auto">
              {application.notes}
            </p>
          </Block>
        )}
      </div>
    </Dialog>
  );
};
