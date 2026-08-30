import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { applyAnalysisDecisions, classificationFromAnalysis } from "../api/analyses";
import { applicationDetailQueryKey, applicationDetailQueryOptions } from "../api/applications";
import { ApiProblem } from "../api/client";
import type { Reason } from "../api/contracts";
import { useWorkflowStage } from "../app/WorkflowLandmark";
import { ActionBar } from "../ui/ActionBar";
import { Button, buttonClasses } from "../ui/Button";
import { Callout } from "../ui/Callout";
import { Card } from "../ui/Card";
import { LtrText } from "../ui/LtrText";
import { PageHeading } from "../ui/PageHeading";
import { StatusBadge } from "../ui/StatusBadge";
import { SummaryList } from "../ui/SummaryList";
import { TechnicalDetails } from "../ui/TechnicalDetails";
import {
  CLASSIFICATION_REASON,
  FIT_REASONS,
  REVIEW_REASONS_THIS_SCREEN_OWNS,
  ReviewDecisionForm,
  emptyDecisions,
  hasDecision,
} from "./ReviewDecisionForm";
import { classificationItems, fitLabels, fitTones, gapSeverityLabels } from "./analysisLabels";
import { actionLabel } from "./applicationLabels";

/* A.4 frame 2: reason navigation, one decision form, the effects summary, Back, and one
   Apply-all-decisions submission. The projection is the source of truth throughout - this
   screen derives no second workflow state machine (A.1). */
export const ReviewPage = () => {
  const { applicationId } = useParams();

  if (applicationId === undefined) {
    throw new Error("ReviewPage rendered without an applicationId route parameter");
  }

  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const query = useQuery(applicationDetailQueryOptions(applicationId));
  const detail = query.data;
  const [decisions, setDecisions] = useState(emptyDecisions);

  useWorkflowStage(detail === undefined ? "unknown" : detail.preparation_state);

  const reasons = detail?.review_reasons ?? [];
  const resolvedHere = (reason: Reason): boolean =>
    reason.allowed_resolution_actions.includes("apply_analysis_decisions") &&
    Object.hasOwn(REVIEW_REASONS_THIS_SCREEN_OWNS, reason.code);
  const mine = reasons.filter(resolvedHere);
  const elsewhere = reasons.filter((reason) => !resolvedHere(reason));
  const showClassification = mine.some((reason) => reason.code === CLASSIFICATION_REASON);
  const showFit = mine.some((reason) => Object.hasOwn(FIT_REASONS, reason.code));

  /* The analysis being decided on is the one the projection calls active, which is also
     the one every review reason names in its entity references. */
  const analysisId = detail?.active_analysis_id ?? null;
  const classification = detail === undefined ? null : classificationFromAnalysis(detail);

  const apply = useMutation({
    mutationFn: async () => {
      if (analysisId === null) {
        throw new Error("apply_analysis_decisions was offered without an active analysis");
      }
      return applyAnalysisDecisions(analysisId, applicationId, decisions);
    },
    onSuccess: async () => {
      /* Nothing from the response body is seeded into the cache. `created_analysis` is
         read as what happened rather than assumed, and the refreshed projection is what
         reports the state that follows. */
      await queryClient.invalidateQueries({ queryKey: applicationDetailQueryKey(applicationId) });
      void navigate(`/applications/${encodeURIComponent(applicationId)}`);
    },
  });

  const back = (
    <Link className={buttonClasses("secondary")} to={`/applications/${encodeURIComponent(applicationId)}`}>
      חזרה למועמדות
    </Link>
  );

  return (
    <Card aria-labelledby="route-heading">
      <PageHeading
        description={
          detail === undefined
            ? "טוען את נימוקי הסקירה…"
            : `${detail.application.company} · ${detail.application.target_role}`
        }
        id="route-heading"
      >
        סקירת הניתוח
      </PageHeading>

      {query.error === null ? null : (
        <Callout
          className="mt-6"
          role="alert"
          title={
            query.error instanceof ApiProblem
              ? query.error.problem.title
              : "לא ניתן לטעון את נימוקי הסקירה"
          }
          tone="blocker"
        >
          {query.error instanceof ApiProblem
            ? query.error.problem.detail
            : "הפנייה לשרת נכשלה. אפשר לרענן את העמוד ולנסות שוב."}
        </Callout>
      )}

      {detail === undefined ? (
        query.error === null ? (
          <p className="mt-6 text-body text-cv-text-muted">טוען את נימוקי הסקירה…</p>
        ) : null
      ) : (
        <div className="mt-6 flex flex-col gap-6">
          {mine.length === 0 && elsewhere.length === 0 ? (
            <Callout title="אין כרגע החלטות שממתינות בסקירה" tone="success">
              מצב המועמדות הוא המקור המדויק, והוא מראה מה הפעולה הבאה.
            </Callout>
          ) : null}

          {/* [2] Reason navigation: the projection's own sentences, unedited. */}
          {mine.map((reason) => (
            <Callout key={reason.code} title="נדרשת החלטה לפני המשך" tone="blocker">
              <p dir="auto">{reason.message}</p>
              <TechnicalDetails className="mt-3">
                <LtrText>{reason.code}</LtrText>
              </TechnicalDetails>
            </Callout>
          ))}

          {/* A review reason this screen does not resolve is named, not dropped. */}
          {elsewhere.map((reason) => (
            <Callout key={reason.code} title="החלטה שנפתרת במסך אחר" tone="warning">
              <p dir="auto">{reason.message}</p>
              {reason.allowed_resolution_actions.length === 0 ? null : (
                <p className="mt-2">
                  הפעולה שפותרת אותה: {reason.allowed_resolution_actions.map(actionLabel).join(" · ")}.
                  המסך שלה עדיין לא נבנה, ואף פקד בטופס הזה אינו פותר אותה.
                </p>
              )}
            </Callout>
          ))}

          {/* [3] What is being decided about, before the controls that change it. */}
          {mine.length === 0 ? null : classification === null ? (
            <Callout title="הסיווג הנוכחי אינו מוצג" tone="neutral">
              הניתוח האחרון של המועמדות אינו הניתוח הפעיל, ולכן הצגתו כאן הייתה מתארת
              החלטה אחרת מזו שנשלחת. ההחלטה עצמה עדיין נשלחת אל הניתוח הפעיל.
            </Callout>
          ) : (
            <section aria-labelledby="current-classification" className="flex flex-col gap-4">
              <div className="flex flex-wrap items-center gap-3">
                <h2 className="text-heading-s font-semibold text-cv-text" id="current-classification">
                  הסיווג הנוכחי
                </h2>
                {classification.fit === null ? null : (
                  <StatusBadge tone={fitTones[classification.fit]}>
                    {fitLabels[classification.fit]}
                  </StatusBadge>
                )}
              </div>
              <SummaryList items={classificationItems(classification)} />
              {classification.gaps.length === 0 ? null : (
                <ul className="flex flex-col gap-2">
                  {classification.gaps.map((gap) => (
                    <li className="text-body" dir="auto" key={`${gap.severity}-${gap.requirement}`}>
                      <span className="font-medium">{gapSeverityLabels[gap.severity]}:</span>{" "}
                      {gap.requirement}
                    </li>
                  ))}
                </ul>
              )}
            </section>
          )}

          {mine.length === 0 ? null : (
            <ReviewDecisionForm
              decisions={decisions}
              disabled={apply.isPending}
              onChange={setDecisions}
              showClassification={showClassification}
              showFit={showFit}
            />
          )}

          {/* [4] Effects summary: what §13 does, and the two things the controls cannot say. */}
          {mine.length === 0 ? null : (
            <Callout title="מה קורה כששולחים את ההחלטות" tone="neutral">
              כל ההחלטות נשלחות יחד בפעולה אחת, שיוצרת ניתוח חדש ובלתי משתנה יחד עם תוכנית
              הבחירה ההתחלתית שלו. הניתוח והתוכנית שעליהם הוחלט נשמרים בדיוק כפי שהם.
              החלטות מצטברות: השארת שדה ריק שומרת על החלטה קודמת ואינה מבטלת אותה. המסך
              אינו מנבא אם ההחלטה סוגרת את הנימוק — מצב המועמדות המעודכן הוא שידווח על כך.
            </Callout>
          )}

          {apply.error === null ? null : (
            <Callout role="alert" title="ההחלטות לא הוחלו" tone="blocker">
              {apply.error instanceof ApiProblem
                ? apply.error.problem.detail
                : "הפנייה לשרת נכשלה. שום החלטה לא נרשמה ואפשר לנסות שוב."}
              {apply.error instanceof ApiProblem ? (
                <TechnicalDetails className="mt-3">
                  <LtrText>{apply.error.problem.code}</LtrText>
                </TechnicalDetails>
              ) : null}
            </Callout>
          )}

          <ActionBar
            /* The bar carries its own top margin only while it is a grouped panel. With
               nothing but the back link it is a plain control, so the separation from the
               decisions above is stated here. */
            className="mt-8"
            primary={
              mine.length === 0 ? (
                back
              ) : (
                <Button
                  disabled={apply.isPending || !hasDecision(decisions) || analysisId === null}
                  onClick={() => apply.mutate()}
                >
                  {apply.isPending ? "מחיל את ההחלטות…" : "החלת כל ההחלטות"}
                </Button>
              )
            }
            secondary={mine.length === 0 ? undefined : back}
          />
        </div>
      )}
    </Card>
  );
};
