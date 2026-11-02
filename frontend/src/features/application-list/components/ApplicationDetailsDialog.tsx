import { ChevronLeft } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import type { ApplicationListItem } from "@/api/contracts";
import { routePaths } from "@/navigation/routePaths";
import {
  confidenceText,
  fitLevelLabel,
  preparationResumeDestination,
  preparationStateLabels,
} from "@/features/preparation";
import { recruitmentStatusLabel } from "@/features/recruitment";
import { buttonClasses } from "@/ui/Button";
import { Dialog } from "@/ui/Dialog";
import { InitialTile } from "@/ui/InitialTile";
import { nextStepText } from "../model/applicationListPresentation";
import { recruitmentStageOf } from "../model/recruitmentStages";

/* One labelled value on a soft tile - four of them in a two-by-two grid, as the design's
   details sheet draws the Application's states. */
const Fact = ({ children, label }: { children: ReactNode; label: string }) => (
  <div className="flex min-w-0 flex-col gap-0.5 rounded-control border border-cv-hairline bg-cv-field-background px-3.5 py-3">
    <span className="text-support text-cv-text-muted">{label}</span>
    <span className="text-label font-bold text-cv-text">{children}</span>
  </div>
);

/* A block with a heading of its own: the next step, the reader's notes. */
const Block = ({ children, label }: { children: ReactNode; label: string }) => (
  <section aria-label={label} className="rounded-control border border-cv-hairline px-4 py-3.5">
    <p className="text-support font-bold text-cv-text-muted">{label}</p>
    <div className="mt-1 text-body text-cv-text">{children}</div>
  </section>
);

const fitText = (application: ApplicationListItem): string => {
  if (application.fit_level == null) return "המשרה טרם נותחה";
  return application.fit_score == null ? fitLevelLabel(application.fit_level) : confidenceText(application.fit_score);
};

/* One Application at a glance, opened from a card in the stages view: who it is for, its
   four states as tiles, the one thing to do next, the reader's notes, and the way into
   the work. It is read from the board's own list item alone, so the sheet cannot say
   something the card does not. Status updates, the posting and the record's commands are
   the Application screen's - the sheet's one command goes there. */
export const ApplicationDetailsDialog = ({
  application,
  onClose,
}: {
  application: ApplicationListItem | null;
  onClose: () => void;
}) => {
  if (application === null) {
    return null;
  }

  const destination = preparationResumeDestination(application);
  const toReady = destination === routePaths.ready(application.id);
  const nextStep = nextStepText(application);

  return (
    <Dialog
      description={<span dir="auto">{application.company}</span>}
      footer={
        <Link className={buttonClasses("primary", "w-full", "large")} onClick={onClose} to={destination}>
          {toReady ? "פתיחת קורות החיים המוכנים" : "המשך בהכנה"}
          <ChevronLeft aria-hidden="true" className="size-icon-md" />
        </Link>
      }
      headingId="application-details-heading"
      onClose={onClose}
      open
      title={
        <span className="flex items-center gap-3">
          <InitialTile name={application.company} />
          <span className="min-w-0">
            <span className="block text-support font-bold text-cv-text-muted">פרטי משרה</span>{" "}
            <span className="block">
              <bdi>{application.target_role}</bdi>
            </span>
          </span>
        </span>
      }
    >
      <div className="flex flex-col gap-3.5">
        <div className="grid grid-cols-2 gap-2.5">
          <Fact label="שלב גיוס">
            {recruitmentStageOf(application.recruitment_status)?.label ??
              recruitmentStatusLabel(application.recruitment_status)}
          </Fact>
          <Fact label="סטטוס משרה">{application.is_closed ? "סגורה" : "פתוחה"}</Fact>
          <Fact label="הכנת קו״ח">{preparationStateLabels[application.preparation_state]}</Fact>
          <Fact label="ציון התאמה">{fitText(application)}</Fact>
        </div>

        {nextStep === null ? null : (
          <Block label="פעולה מומלצת הבאה">
            <p className="font-bold">
              <bdi>{nextStep}</bdi>
            </p>
          </Block>
        )}

        {application.notes === "" ? null : (
          <Block label="הערות">
            <p className="whitespace-pre-wrap" dir="auto">
              {application.notes}
            </p>
          </Block>
        )}
      </div>
    </Dialog>
  );
};
