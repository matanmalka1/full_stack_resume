import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { applicationDetailQueryOptions } from "../api/applications";
import { ApiProblem } from "../api/client";
import type { ApplicationDetail, Reason } from "../api/contracts";
import { useWorkflowStage } from "../app/WorkflowLandmark";
import { buttonClasses } from "../ui/Button";
import { Callout } from "../ui/Callout";
import { Card } from "../ui/Card";
import { LtrText } from "../ui/LtrText";
import { PageHeading } from "../ui/PageHeading";
import { StatusBadge } from "../ui/StatusBadge";
import { SummaryList, type SummaryItem } from "../ui/SummaryList";
import { TechnicalDetails } from "../ui/TechnicalDetails";
import { ApplicationActions } from "./ApplicationActions";
import {
  actionLabel,
  preparationStateLabels,
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

/* Review reasons and stale reasons carry the same shape, and both frame a backend
   sentence rather than replacing it: the message is the server's plain-language
   explanation and the code stays collapsed (A.2). */
const ReasonCallout = ({ reason, title, tone }: { reason: Reason; title: string; tone: "blocker" | "warning" }) => (
  <Callout title={title} tone={tone}>
    <p dir="auto">{reason.message}</p>
    {reason.allowed_resolution_actions.length === 0 ? null : (
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
  /* The landmark follows the projection, and says nothing at all until it arrives. */
  useWorkflowStage(detail === undefined ? "unknown" : detail.preparation_state);

  return (
    <Card aria-labelledby="route-heading">
      <PageHeading
        description={
          detail === undefined
            ? "טוען את מצב המועמדות…"
            : `תפקיד היעד: ${detail.application.target_role}`
        }
        id="route-heading"
      >
        {detail === undefined ? "מועמדות" : detail.application.company}
      </PageHeading>

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
        <div className="mt-6 flex flex-col gap-6">
          <div className="flex flex-wrap items-center gap-3">
            <StatusBadge tone={preparationStateTones[detail.preparation_state]}>
              {preparationStateLabels[detail.preparation_state]}
            </StatusBadge>
            <StatusBadge tone={workingDraftStateTones[detail.working_draft_state]}>
              {workingDraftStateLabels[detail.working_draft_state]}
            </StatusBadge>
          </div>

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
            <ReasonCallout key={reason.code} reason={reason} title="נדרשת החלטה לפני המשך" tone="blocker" />
          ))}

          {detail.stale_reasons.map((reason) => (
            <ReasonCallout
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

          <ApplicationActions detail={detail} />

          {detail.blocked_actions.length === 0 ? null : (
            <TechnicalDetails summary="פעולות שאינן זמינות כעת">
              <SummaryList
                items={detail.blocked_actions.map((blocked) => ({
                  term: actionLabel(blocked.action),
                  value: blocked.reasons.join(" · "),
                  ltr: true,
                }))}
              />
            </TechnicalDetails>
          )}

          <TechnicalDetails>
            <SummaryList items={identifiers(detail)} />
          </TechnicalDetails>
        </div>
      )}
    </Card>
  );
};
