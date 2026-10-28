import { Link } from "react-router-dom";

import type { ApplicationDetail, Reason } from "@/api/contracts";
import { buttonClasses } from "@/ui/Button";
import { Callout } from "@/ui/Callout";
import { Card } from "@/ui/Card";
import { Disclosure } from "@/ui/Disclosure";
import { cx } from "@/ui/cx";
import { ReasonCallout } from "../../components/ReasonCallout";
import { type PreparationScreen, actionDestination, screenPath } from "../../model/actionDestinations";
import {
  type MissingRequirement,
  actionLabel,
  blockedReasonLabel,
  missingRequirement,
  warningDetail,
  warningTitle,
} from "../../model/preparationLabels";

/* The dropped requirement is the posting's own words, often English, so it is isolated in
   <bdi> to keep its direction inside the Hebrew sentence. */
const MissingRequirementDetail = ({ missing }: { missing: MissingRequirement }) => (
  <>
    הדרישה <bdi>{missing.requirementText}</bdi> מכוסה בעובדות שלכם, אבל אף אחת מהן לא נכללה בקורות החיים.
    {missing.others > 0 ? ` ועוד ${missing.others} דרישות חובה במצב דומה.` : null} אפשר לערוך את הטיוטה ולהוסיף שורה
    שמציגה אותה. האזהרה אינה חוסמת אישור.
  </>
);

/* A review reason is reported as a short title plus the control that resolves it. The server's complete message stays
   available behind a disclosure: it is useful evidence when a reader needs it, but does
   not turn several simultaneous reasons into the wall of text this screen used to open
   with. The internal code remains translated rather than exposed as UI vocabulary. */
const ResolvableReasonCallout = ({
  applicationId,
  currentPath,
  fallbackTitle,
  reason,
  tone,
}: {
  applicationId: string;
  /* Where the reader is standing. A resolution that lands back here is not offered: the
     control is already on the screen, and a link to it would be a link to the page the
     reader is reading. A resolution anywhere else is always offered - that is the whole
     point of showing the reason on a screen that cannot answer it. */
  currentPath: string;
  fallbackTitle: string;
  reason: Reason;
  tone: "blocker" | "warning";
}) => {
  const resolution = reason.allowed_resolution_actions
    .map((action) => ({ action, href: actionDestination(action, applicationId) }))
    .find((candidate) => candidate.href !== null && candidate.href !== currentPath);

  return (
    <ReasonCallout
      action={
        resolution?.href == null ? undefined : (
          <Link className={buttonClasses("secondary")} to={resolution.href}>
            {actionLabel(resolution.action)}
          </Link>
        )
      }
      fallbackTitle={fallbackTitle}
      reason={reason}
      tone={tone}
    />
  );
};

/* One alert backdrop with a fixed severity/order: review blockers, warnings, then the
   blocked actions no callout above already explains. There is no staleness to report:
   an outdated approval or check is a state of the document (§6), not a reason here.
   Keeping this region visually quiet lets the action surface beside it remain the clear
   place to continue the workflow. */
export const PreparationAlerts = ({
  aside = false,
  detail,
  screen = "preparation",
  showReviewReasons = true,
}: {
  /* Whether the region is the preparation step's desktop aside: from the large breakpoint
     it then takes the grid's end column beside the work and names itself in view. The
     editor and the ready screen place it in their own flow and leave this off. */
  aside?: boolean;
  detail: ApplicationDetail;
  /* The current screen decides whether a reason's resolution is already beside it. */
  screen?: PreparationScreen;
  /* The editor renders review reasons with their inline resolution controls. */
  showReviewReasons?: boolean;
}) => {
  const currentPath = screenPath(screen, detail.application.id);
  const reviewReasons = showReviewReasons ? detail.review_reasons : [];
  const statedReasonCodes = new Set(detail.review_reasons.map((reason) => reason.code));
  /* `blocked_actions` holds only actions the stage allows and a blocker withholds. A
     reason already stated by its own callout is not repeated once for every action it
     blocks, and a reason with no sentence in the translation table stays quiet until the
     UI has an intentional one. */
  const exceptionalBlockedActions = detail.blocked_actions.flatMap((blocked) => {
    const reasons = blocked.reasons.flatMap((reason) => {
      if (statedReasonCodes.has(reason)) {
        return [];
      }
      const label = blockedReasonLabel(reason);
      return label === null ? [] : [label];
    });
    return reasons.length === 0 ? [] : [{ action: blocked.action, reasons: [...new Set(reasons)] }];
  });
  const hasAlerts = reviewReasons.length > 0 || detail.warnings.length > 0 || exceptionalBlockedActions.length > 0;

  if (!hasAlerts) {
    return null;
  }

  return (
    /* On a phone the backdrop is a rounded, borderless block like the cards around it:
       there the step is a column of cards on the canvas, and a square hairline box read
       as a different kind of thing. */
    /* From the large breakpoint the alerts are the step's aside: the column on the end
       side beside the work, spanning its rows, as the desktop design draws "התראות". */
    <Card
      aria-label="התראות"
      className={cx(
        "flex flex-col gap-3 bg-cv-surface-muted p-3 max-lg:rounded-surface max-lg:border-0 max-lg:p-3.5",
        aside && "lg:col-start-2! lg:row-span-3 lg:row-start-1 lg:ms-5 lg:w-80 lg:rounded-surface lg:border-0 lg:p-4",
      )}
    >
      {/* The aside's name, drawn where it stands apart from the work; on a phone the
          backdrop reads as part of the column and the region's label is enough. */}
      {aside ? (
        <h2 aria-hidden="true" className="text-support font-bold text-cv-text max-lg:hidden">
          התראות
        </h2>
      ) : null}
      {reviewReasons.map((reason) => (
        <ResolvableReasonCallout
          applicationId={detail.application.id}
          currentPath={currentPath}
          fallbackTitle="נדרשת החלטה לפני המשך"
          key={reason.code}
          reason={reason}
          tone="blocker"
        />
      ))}

      {/* A code this build knows says its own sentence, in the open, exactly as the ready
          screen already says it - `warningDetail` is the table both read from, and this
          was the one call site that skipped it and printed the server's raw string
          instead. So the same warning was a localized line on one step of the workflow
          and an English line behind a press on another. A code with no entry keeps the
          disclosure, which is this screen's rule for an unlocalized server message: the
          evidence stays reachable without several of them becoming a wall of text. */}
      {detail.warnings.map((warning) => {
        const localized = warningDetail(warning.code, "");
        const missing = warning.code === "REQUIREMENT_NOT_IN_DOCUMENT" ? missingRequirement(warning, detail) : null;
        /* The older-analysis warning has an explicit answer, `build_from_analysis`, which
           lives beside the analysis. Offered from another screen only while the projection
           offers the action, and never as a link to the screen the reader is on. */
        const rebuildHref =
          warning.code === "DOCUMENT_ON_OLDER_ANALYSIS" && detail.available_actions.includes("build_from_analysis")
            ? actionDestination("build_from_analysis", detail.application.id)
            : null;

        return (
          <Callout
            action={
              rebuildHref === null || rebuildHref === currentPath ? undefined : (
                <Link className={buttonClasses("secondary")} to={rebuildHref}>
                  {actionLabel("build_from_analysis")}
                </Link>
              )
            }
            key={warning.code}
            title={warningTitle(warning.code)}
            tone="warning"
          >
            {missing !== null ? (
              <MissingRequirementDetail missing={missing} />
            ) : localized === "" ? (
              <Disclosure summary="פרטי האזהרה">
                <p dir="auto">{warning.message}</p>
              </Disclosure>
            ) : (
              localized
            )}
          </Callout>
        );
      })}

      {exceptionalBlockedActions.map((blocked) => (
        <Callout key={blocked.action} title={`הפעולה ${actionLabel(blocked.action)} חסומה כרגע`} tone="blocker">
          <ul className="flex list-disc flex-col gap-1 ps-5">
            {blocked.reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        </Callout>
      ))}
    </Card>
  );
};
