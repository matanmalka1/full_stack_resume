import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { classificationFromAnalysis } from "@/api/analyses";
import { documentQueryOptions } from "@/api/documents";
import { QueryState } from "@/ui/QueryState";
import { actionLabel } from "../model/preparationLabels";
import { Callout } from "@/ui/Callout";
import { WideRow } from "@/ui/WideRow";
import { cx } from "@/ui/cx";
import type { AnalysisDecisions, ApplicationDetail } from "@/api/contracts";
import { workflowActionPlan } from "../model/workflowActionPlan";
import { AnalysisStage } from "../stages/analysis/AnalysisStage";
import { DocumentSelectionPanel } from "../stages/content/DocumentSelectionPanel";
import { VerificationStage } from "../stages/verification/VerificationStage";
import { MatchingConfigurationEditor } from "../stages/matching/MatchingConfigurationEditor";
import { AnalysisStatusBanner } from "./AnalysisStatusBanner";
import { AutomaticDraftNotice } from "./AutomaticDraftNotice";

export const PreparationView = ({
  detail,
  onQueued,
  operationLive,
}: {
  detail: ApplicationDetail;
  onQueued: (operationId: string) => void;
  operationLive: boolean;
}) => {
  const [matchingSaved, setMatchingSaved] = useState<AnalysisDecisions | null>(null);
  /* The confirmation describes the projection the save returned; once the screen's own
     projection has moved past it, it is no longer news about what is on screen. */
  const matchingSaveInContext =
    matchingSaved?.application_id === detail.application.id &&
    matchingSaved.state.latest_analysis_id === detail.latest_analysis_id &&
    matchingSaved.state.document_hash === detail.document_hash;
  const classification = classificationFromAnalysis(detail);
  const supersededAnalysis = classification === null && detail.latest_analysis != null;

  const plan = workflowActionPlan(detail);
  const hasRecommendation = detail.recommended_action != null;
  const selectionAction = plan.selection;
  /* The fact selection is the document's own, so it is read from the document - which
     exists from the first analysis on. */
  const documentQuery = useQuery({
    ...documentQueryOptions(detail.application.id),
    enabled: selectionAction !== null,
  });
  const hasMainColumn = classification !== null || selectionAction !== null;

  return (
    <div className="flex flex-col gap-4">
      <AutomaticDraftNotice detail={detail} />

      <AnalysisStatusBanner classification={classification} supersededAnalysis={supersededAnalysis} />

      <WideRow>
        <div className="flex flex-col gap-6 lg:flex-row-reverse lg:items-start lg:gap-8 xl:gap-10">
          <div
            className={cx(
              "flex min-w-0 flex-col gap-6",
              hasMainColumn ? "lg:sticky lg:top-20 lg:basis-2/5 xl:basis-1/3" : "lg:flex-1",
            )}
          >
            <VerificationStage
              detail={detail}
              hasRecommendation={hasRecommendation}
              onQueued={onQueued}
              operationLive={operationLive}
              plan={plan}
            />

            {classification === null ? null : (
              // A new analysis or document remounts the form so stale choices are never submitted.
              <MatchingConfigurationEditor
                classification={classification}
                detail={detail}
                key={`${detail.latest_analysis_id ?? "none"}:${detail.document_hash ?? "none"}`}
                onSaved={setMatchingSaved}
              />
            )}

            {matchingSaveInContext && matchingSaved !== null && (
              // oxlint-disable-next-line jsx-a11y/prefer-tag-over-role
              <Callout role="status" title="הגדרות ההתאמה נשמרו" tone="success">
                {matchingSaved.state.recommended_action == null
                  ? "מצב המועמדות עודכן לפי ההקשר החדש."
                  : `הצעד הבא לפי השרת: ${actionLabel(matchingSaved.state.recommended_action)}.`}
              </Callout>
            )}
          </div>

          {hasMainColumn ? (
            <div className="flex min-w-0 flex-1 flex-col gap-6">
              {classification === null ? null : (
                <AnalysisStage
                  classification={classification}
                  detail={detail}
                  onQueued={onQueued}
                  operationLive={operationLive}
                  plan={plan}
                />
              )}

              {selectionAction === null ? null : (
                <QueryState
                  error={documentQuery.error}
                  fallbackDetail="לא ניתן לקרוא את בחירת העובדות של המסמך. המסמך לא השתנה."
                  fallbackTitle="בחירת העובדות לא נטענה"
                  loading={documentQuery.data === undefined}
                  loadingLabel="טוען את בחירת העובדות…"
                >
                  {documentQuery.data === undefined ? null : (
                    <DocumentSelectionPanel
                      detail={detail}
                      document={documentQuery.data.document}
                      emphasized={selectionAction.emphasized}
                      onQueued={onQueued}
                      operationLive={operationLive}
                      requirements={classification?.requirements ?? []}
                    />
                  )}
                </QueryState>
              )}
            </div>
          ) : null}
        </div>
      </WideRow>
    </div>
  );
};
