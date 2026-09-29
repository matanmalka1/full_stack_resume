import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { classificationFromAnalysis } from "@/api/analyses";
import { documentQueryOptions } from "@/api/documents";
import { QueryState } from "@/ui/QueryState";
import { actionLabel } from "../model/preparationLabels";
import { SuccessNotice } from "@/ui/SuccessNotice";
import { WideRow } from "@/ui/WideRow";
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

  return (
    <div className="flex flex-col gap-4">
      <AutomaticDraftNotice detail={detail} />

      <AnalysisStatusBanner classification={classification} supersededAnalysis={supersededAnalysis} />

      <WideRow>
        {/* One column: what needs deciding first, then the analysis and the fact selection
            at the full width of the row. The step's action is not here - its commit bar
            portals to the shell's action slot. */}
        <div className="flex min-w-0 flex-col gap-6">
          <VerificationStage
            detail={detail}
            hasRecommendation={hasRecommendation}
            onQueued={onQueued}
            operationLive={operationLive}
            plan={plan}
          />

          {matchingSaveInContext && matchingSaved !== null && (
            <SuccessNotice onDismiss={() => setMatchingSaved(null)} title="הגדרות ההתאמה נשמרו">
              {matchingSaved.state.recommended_action == null
                ? "מצב המועמדות עודכן בהתאם."
                : `הצעד הבא: ${actionLabel(matchingSaved.state.recommended_action)}.`}
            </SuccessNotice>
          )}

          {classification === null ? null : (
            <AnalysisStage
              classification={classification}
              detail={detail}
              headerContent={
                // A new analysis or document remounts the form so stale choices are never submitted.
                <MatchingConfigurationEditor
                  classification={classification}
                  detail={detail}
                  key={`${detail.latest_analysis_id ?? "none"}:${detail.document_hash ?? "none"}`}
                  onSaved={setMatchingSaved}
                />
              }
              onQueued={onQueued}
              operationLive={operationLive}
              plan={plan}
            />
          )}

          {selectionAction === null ? null : (
            <QueryState
              error={documentQuery.error}
              errorDetail="המסמך לא השתנה. אפשר לרענן את העמוד ולנסות שוב."
              errorTitle="לא ניתן לטעון את בחירת העובדות"
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
      </WideRow>
    </div>
  );
};
