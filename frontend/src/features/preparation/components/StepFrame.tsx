import { ChevronRight } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import type { ApplicationDetail } from "@/api/contracts";
import { useIsPhone } from "@/features/operations";
import { PhoneActionBar } from "@/ui/PhoneActionBar";
import { Skeleton } from "@/ui/Skeleton";
import { cx } from "@/ui/cx";
import type { WorkflowStage } from "../model/workflowStages";
import { useWorkflowSteps } from "./PreparationWorkflowSteps";
import { WorkflowStepsRail } from "./WorkflowStepsRail";

interface StepFrameProps {
  /* The step's commands. From the large breakpoint they sit at the end of the heading row;
     on a phone they are the bar pinned to the bottom of the screen. */
  actions?: ReactNode;
  applicationId: string;
  /* Where the chevron beside the heading leads, and what it is called. */
  back: { label: string; to: string };
  children: ReactNode;
  /* Absent while the projection is in flight; the header then holds the line it will
     fill rather than moving the heading when it arrives. */
  detail: ApplicationDetail | undefined;
  /* "form" is the shorter reading measure of a screen whose body is one card of inputs. */
  measure?: "wide" | "form";
  /* Whether the step's heading stays visible on a phone. Off, the compact header names
     whose CV it is and the stage band under it says which step this is, so the heading
     stays for assistive tech and route focus only. */
  phoneHeading?: boolean;
  /* Whether the stage rail is drawn. A screen beneath a step - the matching settings -
     keeps a phone's stage band but names its position in the wide subtitle instead. */
  rail?: boolean | "phone";
  stage: WorkflowStage;
  /* Replaces the subtitle under a wide screen's heading (role · company by default). */
  subtitle?: ReactNode;
  title: ReactNode;
}

/* The frame every preparation screen after intake is drawn in, as the design draws it.

   A wide screen: a bordered square back to where the step was opened from, the heading
   with whose CV it is under it, the step's commands at the row's end, and the stage rail
   in a card below. A phone: the inner screen's compact header - a chevron, the role and
   the company - the stage band under it, and the commands in a bar on the bottom edge. */
export const StepFrame = ({
  actions,
  applicationId,
  back,
  children,
  detail,
  measure = "wide",
  phoneHeading = false,
  rail = true,
  stage,
  subtitle,
  title,
}: StepFrameProps) => {
  const isPhone = useIsPhone();
  const steps = useWorkflowSteps(stage, applicationId, detail);
  const role = detail?.application.target_role;
  const company = detail?.application.company;

  return (
    <section
      aria-labelledby="route-heading"
      className={cx("page-frame flex flex-col gap-5 max-lg:gap-3.5", measure === "form" && "[--page-measure:55rem]")}
    >
      {/* One wrapping row whose parts are ordered per width: a wide screen reads back,
          heading, commands, then the rail on a row of its own; a phone reads the chevron
          and whose CV it is, the stage band, then the heading where the step shows one.
          Ordering keeps a single heading in the document at every width. */}
      <header className="flex flex-wrap items-center gap-x-3.5 gap-y-5 max-lg:-mt-1.5 max-lg:gap-x-1 max-lg:gap-y-3.5">
        <Link
          aria-label={back.label}
          className="order-1 flex size-10 shrink-0 items-center justify-center rounded-control-sm border border-cv-border bg-cv-surface text-cv-text transition-colors hover:bg-cv-surface-muted max-lg:-ms-2 max-lg:size-11 max-lg:rounded-control max-lg:border-0 max-lg:bg-transparent"
          to={back.to}
        >
          <ChevronRight aria-hidden="true" className="size-icon-lg max-lg:size-5.5" />
        </Link>

        {/* Who the CV is for, as a phone's header names it. Drawn for sighted readers: the
            heading and the subtitle under it say the same in words. */}
        <div aria-hidden="true" className="order-2 min-w-0 flex-1 lg:hidden">
          {detail === undefined ? (
            <Skeleton className="block h-5 w-40" />
          ) : (
            <>
              <p className="truncate text-heading-sm font-extrabold text-cv-text" dir="auto">
                {role}
              </p>
              <p className="truncate text-caption text-cv-text-muted" dir="auto">
                {company}
              </p>
            </>
          )}
        </div>

        <div
          className={cx(
            "min-w-50 flex-1 lg:order-2",
            phoneHeading ? "max-lg:order-4 max-lg:basis-full" : "max-lg:sr-only",
          )}
        >
          <h1
            className="text-title font-extrabold tracking-tight text-cv-text"
            data-route-heading
            dir="auto"
            id="route-heading"
            tabIndex={-1}
          >
            {title}
          </h1>
          <p className="mt-0.5 text-label text-cv-text-muted max-lg:sr-only" dir="auto">
            {subtitle ??
              (detail === undefined ? <Skeleton className="inline-block w-48 align-middle" /> : `${role} · ${company}`)}
          </p>
        </div>

        {actions === undefined || isPhone ? null : (
          <div className="flex flex-wrap items-center gap-3 lg:order-3">{actions}</div>
        )}

        {rail === false ? null : (
          <div className={cx("order-3 basis-full lg:order-4", rail === "phone" && "lg:hidden")}>
            <WorkflowStepsRail label="שלבי הכנת קורות החיים" steps={steps} />
          </div>
        )}
      </header>

      {children}

      {actions !== undefined && isPhone ? <PhoneActionBar>{actions}</PhoneActionBar> : null}
    </section>
  );
};
