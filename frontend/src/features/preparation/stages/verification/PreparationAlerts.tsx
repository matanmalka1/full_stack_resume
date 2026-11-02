import { TriangleAlert } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import type { ApplicationDetail, Reason } from "@/api/contracts";
import { buttonClasses } from "@/ui/Button";
import { Callout } from "@/ui/Callout";
import { Card } from "@/ui/Card";
import { Disclosure } from "@/ui/Disclosure";
import { ReasonCallout } from "../../components/ReasonCallout";
import { type PreparationScreen, actionDestination, screenPath } from "../../model/actionDestinations";
import {
  type MissingRequirement,
  actionLabel,
  blockedReasonLabel,
  missingRequirement,
  reasonTitle,
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

/* `blocked_actions` holds only actions the stage allows and a blocker withholds. A reason
   already stated by its own callout is not repeated once for every action it blocks, and a
   reason with no sentence in the translation table stays quiet until the UI has an
   intentional one. */
const exceptionalBlockedActions = (detail: ApplicationDetail) => {
  const statedReasonCodes = new Set(detail.review_reasons.map((reason) => reason.code));
  return detail.blocked_actions.flatMap((blocked) => {
    const reasons = blocked.reasons.flatMap((reason) => {
      if (statedReasonCodes.has(reason)) {
        return [];
      }
      const label = blockedReasonLabel(reason);
      return label === null ? [] : [label];
    });
    return reasons.length === 0 ? [] : [{ action: blocked.action, reasons: [...new Set(reasons)] }];
  });
};

/* Whether the region has anything to say, for a caller that lays out a column around it. */
export const hasPreparationAlerts = (detail: ApplicationDetail, showReviewReasons = true): boolean =>
  (showReviewReasons && detail.review_reasons.length > 0) ||
  detail.warnings.length > 0 ||
  exceptionalBlockedActions(detail).length > 0;

/* One alert in the compact list: its title, the sentence behind it folded under a press,
   and the way to the control that answers it where one exists elsewhere. */
const CompactAlert = ({ action, children, title }: { action?: ReactNode; children?: ReactNode; title: string }) => (
  <li className="flex items-start gap-2.5">
    <TriangleAlert aria-hidden="true" className="mt-0.5 size-icon-lg shrink-0 text-cv-text" />
    <div className="flex min-w-0 flex-col items-start gap-1">
      <p className="text-label font-bold text-cv-text">{title}</p>
      {children === undefined ? null : (
        <details className="group text-support text-cv-text-muted">
          <summary className="w-fit cursor-pointer list-none text-cv-text underline underline-offset-4 [&::-webkit-details-marker]:hidden">
            פרטי האזהרה
          </summary>
          <div className="mt-1.5 leading-relaxed">{children}</div>
        </details>
      )}
      {action}
    </div>
  </li>
);

/* One alert backdrop with a fixed severity/order: review blockers, warnings, then the
   blocked actions no callout above already explains. There is no staleness to report:
   an outdated approval or check is a state of the document (§6), not a reason here.
   Keeping this region visually quiet lets the action surface beside it remain the clear
   place to continue the workflow. */
export const PreparationAlerts = ({
  compact = false,
  detail,
  screen = "preparation",
  showReviewReasons = true,
}: {
  /* The verification step's quiet list: one line per alert, its sentence folded under a
     press, instead of a callout each. */
  compact?: boolean;
  detail: ApplicationDetail;
  /* The current screen decides whether a reason's resolution is already beside it. */
  screen?: PreparationScreen;
  /* The editor renders review reasons with their inline resolution controls. */
  showReviewReasons?: boolean;
}) => {
  const currentPath = screenPath(screen, detail.application.id);
  const reviewReasons = showReviewReasons ? detail.review_reasons : [];
  const blockedActions = exceptionalBlockedActions(detail);

  if (!hasPreparationAlerts(detail, showReviewReasons)) {
    return null;
  }

  const rebuildHrefFor = (code: string) =>
    code === "DOCUMENT_ON_OLDER_ANALYSIS" && detail.available_actions.includes("build_from_analysis")
      ? actionDestination("build_from_analysis", detail.application.id)
      : null;

  if (compact) {
    const actionLink = (href: string | null, action: string) =>
      href === null || href === currentPath ? undefined : (
        <Link className="text-support font-bold text-cv-text underline underline-offset-4" to={href}>
          {actionLabel(action)}
        </Link>
      );

    return (
      <section
        aria-labelledby="preparation-alerts-heading"
        className="flex flex-col gap-3 rounded-surface bg-cv-surface-muted p-4"
      >
        <h2 className="text-support font-bold text-cv-text-muted" id="preparation-alerts-heading">
          התראות
        </h2>
        <ul className="flex flex-col gap-3">
          {reviewReasons.map((reason) => {
            const resolution = reason.allowed_resolution_actions
              .map((action) => ({ action, href: actionDestination(action, detail.application.id) }))
              .find((candidate) => candidate.href !== null && candidate.href !== currentPath);
            return (
              <CompactAlert
                action={resolution === undefined ? undefined : actionLink(resolution.href, resolution.action)}
                key={reason.code}
                title={reasonTitle(reason.code, "נדרשת החלטה לפני המשך")}
              >
                <p dir="auto">{reason.message}</p>
              </CompactAlert>
            );
          })}
          {detail.warnings.map((warning) => {
            const localized = warningDetail(warning.code, "");
            const missing = warning.code === "REQUIREMENT_NOT_IN_DOCUMENT" ? missingRequirement(warning, detail) : null;
            return (
              <CompactAlert
                action={actionLink(rebuildHrefFor(warning.code), "build_from_analysis")}
                key={warning.code}
                title={warningTitle(warning.code)}
              >
                {missing !== null ? (
                  <MissingRequirementDetail missing={missing} />
                ) : localized === "" ? (
                  <p dir="auto">{warning.message}</p>
                ) : (
                  localized
                )}
              </CompactAlert>
            );
          })}
          {blockedActions.map((blocked) => (
            <CompactAlert key={blocked.action} title={`הפעולה ${actionLabel(blocked.action)} חסומה כרגע`}>
              <ul className="flex list-disc flex-col gap-1 ps-5">
                {blocked.reasons.map((reason) => (
                  <li key={reason}>{reason}</li>
                ))}
              </ul>
            </CompactAlert>
          ))}
        </ul>
      </section>
    );
  }

  return (
    /* On a phone the backdrop is a rounded, borderless block like the cards around it:
       there the step is a column of cards on the canvas, and a square hairline box read
       as a different kind of thing. */
    <Card
      aria-label="התראות"
      className="flex flex-col gap-3 bg-cv-surface-muted p-3 max-lg:rounded-surface max-lg:border-0 max-lg:p-3.5"
    >
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
        const rebuildHref = rebuildHrefFor(warning.code);

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

      {blockedActions.map((blocked) => (
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
