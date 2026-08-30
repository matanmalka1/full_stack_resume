import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { classificationFromAnalysis } from "../api/analyses";
import { applicationDetailQueryOptions } from "../api/applications";
import { ApiProblem } from "../api/client";
import type { ApplicationDetail, BlockedAction, Reason } from "../api/contracts";
import { useWorkflowStage } from "../app/WorkflowLandmark";
import { buttonClasses } from "../ui/Button";
import { Callout } from "../ui/Callout";
import { Card } from "../ui/Card";
import { LtrText } from "../ui/LtrText";
import { PageHeading } from "../ui/PageHeading";
import { StatusBadge } from "../ui/StatusBadge";
import { SummaryList, type SummaryItem } from "../ui/SummaryList";
import { TechnicalDetails } from "../ui/TechnicalDetails";
import { AnalysisPanel, SupersededAnalysisNote } from "./AnalysisPanel";
import { ApplicationActions } from "./ApplicationActions";
import { actionDestination } from "./actionDestinations";
import {
  actionLabel,
  blockedReasonLabel,
  preparationStateLabels,
  preparationStateNextStep,
  preparationStateTones,
  workingDraftStateLabels,
  workingDraftStateTones,
} from "./applicationLabels";

const identifiers = (detail: ApplicationDetail): SummaryItem[] => {
  const items: SummaryItem[] = [
    { term: "מזהה המועמדות", value: detail.application.id, ltr: true },
    { term: "תצלום המשרה הפעיל", value: detail.active_job_snapshot_id, ltr: true },
    { term: "מצב הגיוס", value: detail.recruitment_status, ltr: true },
  ];
  const optional: [string, string | null | undefined][] = [
    ["הניתוח הפעיל", detail.active_analysis_id],
    ["תוכנית הבחירה הפעילה", detail.active_selection_plan_id],
    ["הטיוטה הפעילה", detail.active_working_draft_id],
    ["הגרסה המאושרת האחרונה", detail.latest_approved_revision_id],
    ["הגרסה המוכנה האחרונה", detail.latest_ready_revision_id],
  ];

  for (const [term, value] of optional) {
    if (value != null) {
      items.push({ term, value, ltr: true });
    }
  }

  return items;
};

/* A blocked action is worth reporting only when its blocker is not already the plain
   reading of the stage the screen is showing.

   Every action downstream of where the workflow has got to is blocked, by definition, and
   listing all of them restated the landmark once per row: fourteen sentences of "there is
   no active draft" on a screen whose own badge says there is no active draft. What is
   worth a row is the blocker that does not follow from the stage - a draft that exists
   but failed validation, an approval waiting on a validation run - because that one names
   something the user has to act on rather than something they have simply not reached.

   The codes are the projection's, so an unrecognised one is kept rather than filtered:
   silence about a blocker nobody anticipated is the failure this list exists to avoid. */
const IMPLIED_BY_STAGE = new Set([
  "NO_REVIEW_DECISION_REQUIRED",
  "ANALYSIS_OR_SELECTION_PLAN_REQUIRED",
  "WORKING_DRAFT_REQUIRED",
  "VALIDATED_DRAFT_REQUIRED",
  "APPROVED_REVISION_REQUIRED",
  "ACTION_NOT_AVAILABLE",
]);

const noteworthyBlockedActions = (detail: ApplicationDetail): BlockedAction[] =>
  detail.blocked_actions.filter((blocked) =>
    blocked.reasons.some((reason) => !IMPLIED_BY_STAGE.has(reason)),
  );

/* `working_draft_state === "none"` is news only once a draft could exist. At the stages
   below it restates the preparation stage, and the masthead is the worst place for a
   restatement: two badges of equal weight read as two independent facts.

   The conjunction with `none` is what keeps this honest, because the stage alone does not
   settle it. `ready_to_draft` is reached by two paths - no draft at all, and a draft whose
   sources went stale - so it implies nothing about a draft on its own. The stale path
   reports `stale` rather than `none` and keeps its badge; only the empty one is silent. */
const IMPLIES_NO_DRAFT = new Set(["needs_analysis", "needs_review", "ready_to_draft"]);

const draftStateIsImplied = (detail: ApplicationDetail): boolean =>
  detail.working_draft_state === "none" && IMPLIES_NO_DRAFT.has(detail.preparation_state);

/* Review reasons and stale reasons carry the same shape, and both frame a backend
   sentence rather than replacing it: the message is the server's plain-language
   explanation and the code stays collapsed (A.2).

   Whether the resolving action has a screen is asked of `actionDestination` rather than
   asserted here, so a reason cannot go on promising a screen that now exists. */
const ReasonCallout = ({
  applicationId,
  reason,
  title,
  tone,
}: {
  applicationId: string;
  reason: Reason;
  title: string;
  tone: "blocker" | "warning";
}) => {
  const resolution = reason.allowed_resolution_actions
    .map((action) => ({ action, href: actionDestination(action, applicationId) }))
    .find((candidate) => candidate.href !== null);

  return (
    <Callout
      action={
        resolution?.href == null ? undefined : (
          <Link className={buttonClasses("secondary")} to={resolution.href}>
            {actionLabel(resolution.action)}
          </Link>
        )
      }
      title={title}
      tone={tone}
    >
      <p dir="auto">{reason.message}</p>
      {reason.allowed_resolution_actions.length === 0 || resolution !== undefined ? null : (
        <p className="mt-2">
          הפעולה שפותרת אותה: {reason.allowed_resolution_actions.map(actionLabel).join(" · ")}.
          המסך שלה מגיע בפרוסה הבאה.
        </p>
      )}
      <TechnicalDetails className="mt-3">
        <LtrText>{reason.code}</LtrText>
      </TechnicalDetails>
    </Callout>
  );
};

/* A.1: the fixed context screen for one Application. It is not a redirect that routes by
   stage - an existing Application can be anywhere in its lifecycle, and choosing a
   destination for it here would be the second workflow state machine the information
   architecture forbids. It renders the §9 projection and offers the actions the
   projection reports. */
export const ApplicationPage = () => {
  const { applicationId } = useParams();

  /* The route is applications/:applicationId, so a missing id is a router invariant
     violation rather than a state this screen supports. */
  if (applicationId === undefined) {
    throw new Error("ApplicationPage rendered without an applicationId route parameter");
  }

  const query = useQuery(applicationDetailQueryOptions(applicationId));
  const detail = query.data;
  const noteworthy = detail === undefined ? [] : noteworthyBlockedActions(detail);
  /* The same narrow read the review screen uses, and the same guard: it answers `null`
     unless the analysis on record is the active one, so a superseded analysis is named
     as superseded rather than shown as the classification in force. */
  const classification = detail === undefined ? null : classificationFromAnalysis(detail);
  const supersededAnalysis =
    detail !== undefined && classification === null && detail.latest_analysis != null;
  /* The landmark follows the projection, and says nothing at all until it arrives. */
  useWorkflowStage(detail === undefined ? "unknown" : detail.preparation_state);

  return (
    <Card aria-labelledby="route-heading">
      {/* The persistent shell already names the company and role. This masthead names
          the page and reports its two state axes without repeating that context. */}
      <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3 border-b border-cv-border pb-4">
        <div className="min-w-0">
          <PageHeading
            description={detail === undefined ? "טוען את מצב המועמדות…" : undefined}
            id="route-heading"
          >
            מצב המועמדות
          </PageHeading>
        </div>
        {detail === undefined ? null : (
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge tone={preparationStateTones[detail.preparation_state]}>
              {preparationStateLabels[detail.preparation_state]}
            </StatusBadge>
            {/* The draft axis is reported only where it says something the preparation
                stage does not. Before the analysis exists a draft cannot, so "there is no
                active draft" beside "waiting for the job analysis" is the same
                redundancy `IMPLIED_BY_STAGE` removes from the blocked-action list - and
                it costs a badge in the masthead, which is where the screen's two states
                are supposed to be distinguishable at a glance. */}
            {draftStateIsImplied(detail) ? null : (
              <StatusBadge tone={workingDraftStateTones[detail.working_draft_state]}>
                {workingDraftStateLabels[detail.working_draft_state]}
              </StatusBadge>
            )}
          </div>
        )}
      </div>

      {query.error === null ? null : (
        <Callout
          className="mt-6"
          role="alert"
          title={
            query.error instanceof ApiProblem
              ? query.error.problem.title
              : "לא ניתן לטעון את מצב המועמדות"
          }
          tone="blocker"
        >
          {query.error instanceof ApiProblem
            ? query.error.problem.detail
            : "הפנייה לשרת נכשלה. אפשר לרענן את העמוד ולנסות שוב."}
          {query.error instanceof ApiProblem ? (
            <TechnicalDetails className="mt-3">
              <LtrText>{query.error.problem.code}</LtrText>
            </TechnicalDetails>
          ) : null}
        </Callout>
      )}

      {detail === undefined ? (
        query.error === null ? (
          <p className="mt-6 text-body text-cv-text-muted">טוען את מצב המועמדות…</p>
        ) : null
      ) : (
        <div className="mt-5 flex flex-col gap-5">
          {detail.active_operation == null ? null : (
            <Callout
              action={
                <Link
                  className={buttonClasses("secondary")}
                  to={`/operations/${encodeURIComponent(detail.active_operation.id)}`}
                >
                  מעבר למצב הפעולה
                </Link>
              }
              title="פעולה רצה על המועמדות הזו"
              tone="progress"
            >
              עד שהיא מסתיימת, מצב המועמדות כאן מתעדכן מעצמו.
            </Callout>
          )}

          {detail.review_reasons.map((reason) => (
            <ReasonCallout
              applicationId={detail.application.id}
              key={reason.code}
              reason={reason}
              title="נדרשת החלטה לפני המשך"
              tone="blocker"
            />
          ))}

          {detail.stale_reasons.map((reason) => (
            <ReasonCallout
              applicationId={detail.application.id}
              key={reason.code}
              reason={reason}
              title="הטיוטה אינה מעודכנת מול המקורות שלה"
              tone="warning"
            />
          ))}

          {detail.warnings.map((warning) => (
            <Callout key={warning.code} title="אפשר להמשיך, אך יש לשים לב" tone="warning">
              <p dir="auto">{warning.message}</p>
              <TechnicalDetails className="mt-3">
                <LtrText>{warning.code}</LtrText>
              </TechnicalDetails>
            </Callout>
          ))}

          {detail.newer_draft_in_progress ? (
            <Callout title="קיימת טיוטה חדשה יותר מהגרסה שאושרה" tone="warning">
              הגרסה שאושרה נשמרת בדיוק כפי שהיא. הטיוטה החדשה היא עבודה נפרדת ואינה משנה
              אותה.
            </Callout>
          ) : null}

          {/* What the analysis concluded, above the control that acts on it. It is the
              reasoning behind the stage the masthead reports, so it belongs on this
              screen rather than on a route the reader would have to leave for. */}
          {classification === null ? null : (
            <AnalysisPanel classification={classification} detail={detail} />
          )}

          {supersededAnalysis ? <SupersededAnalysisNote /> : null}

          {/* What the workflow is waiting on, in front of the control rather than behind a
              disclosure. Without it the card body was a single button in an empty box,
              and the only text explaining it was fourteen collapsed rows of blockers. */}
          <p className="text-body leading-7 text-cv-text-muted" dir="auto">
            {preparationStateNextStep[detail.preparation_state]}
          </p>

          <ApplicationActions detail={detail} />

          {/* Only the blockers that are not already implied by the stage. Listing every
              later action of the workflow as "unavailable" said nothing the landmark and
              the offered action did not already say, and it buried the identifiers - the
              one thing in here that is genuinely technical - under fourteen rows of it. */}
          <TechnicalDetails>
            <div className="flex flex-col gap-4">
              {noteworthy.length === 0 ? null : (
                <div>
                  <p className="mb-2 font-semibold text-cv-text">פעולות שאינן זמינות כעת</p>
                  <SummaryList
                    items={noteworthy.map((blocked) => ({
                      term: actionLabel(blocked.action),
                      value: blocked.reasons.map(blockedReasonLabel).join(" "),
                    }))}
                  />
                </div>
              )}
              <div>
                <p className="mb-2 font-semibold text-cv-text">מזהי הרשומות</p>
                <SummaryList items={identifiers(detail)} />
              </div>
            </div>
          </TechnicalDetails>
        </div>
      )}
    </Card>
  );
};
