import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useMemo } from "react";
import { useNavigate } from "react-router-dom";

import { startAnalysis } from "../api/applications";
import { ApiProblem } from "../api/client";
import type { ApplicationDetail } from "../api/contracts";
import { operationQueryKey } from "../api/operations";
import { ActionBar } from "../ui/ActionBar";
import { Button } from "../ui/Button";
import { Callout } from "../ui/Callout";
import { LtrText } from "../ui/LtrText";
import { TechnicalDetails } from "../ui/TechnicalDetails";
import { actionLabel } from "./applicationLabels";

interface ApplicationActionsProps {
  detail: ApplicationDetail;
}

const mutationMessage = (error: unknown): string =>
  error instanceof ApiProblem
    ? error.problem.detail
    : "לא ניתן להפעיל את הפעולה. מצב המועמדות לא השתנה ואפשר לנסות שוב.";

/* A.1: the actions come from the projection. This screen implements `analyze`; any other
   action the backend recommends is named and reported as not yet built, because
   inventing a destination for it would be exactly the second workflow state machine the
   information architecture forbids. */
export const ApplicationActions = ({ detail }: ApplicationActionsProps) => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const snapshotId = detail.active_job_snapshot_id;
  /* One key per snapshot: an answer that never arrived can be sent again without
     queueing a second analysis of the same posting. */
  const analyzeKey = useMemo(() => crypto.randomUUID(), [snapshotId]);

  const analyze = useMutation({
    mutationFn: () => startAnalysis(detail.application.id, snapshotId, analyzeKey),
    onSuccess: ({ operation, operationPath }) => {
      /* The accepted representation is the Operation screen's first state, so it is
         seeded rather than fetched a second time. */
      queryClient.setQueryData(operationQueryKey(operation.id), operation);
      void navigate(operationPath);
    },
  });

  const recommended = detail.recommended_action ?? null;
  const canAnalyze = detail.available_actions.includes("analyze");
  const analyzeRecommended = recommended === "analyze";

  return (
    <div className="flex flex-col gap-4">
      {analyze.error === null ? null : (
        <Callout role="alert" title="הפעולה לא בוצעה" tone="blocker">
          {mutationMessage(analyze.error)}
          {analyze.error instanceof ApiProblem ? (
            <TechnicalDetails className="mt-3">
              <LtrText>{analyze.error.problem.code}</LtrText>
            </TechnicalDetails>
          ) : null}
        </Callout>
      )}

      {recommended === null || analyzeRecommended ? null : (
        <Callout title={`הפעולה המומלצת כעת היא ${actionLabel(recommended)}`} tone="neutral">
          המסך שלה עדיין לא נבנה והוא מגיע בפרוסה הבאה. מצב המועמדות שלמעלה הוא המקור
          המדויק, ושום פעולה אינה מופעלת מעצמה.
        </Callout>
      )}

      {/* Re-analysis destroys nothing: the existing JobAnalysis and any active draft are
          immutable records that stay exactly as they are. What changes is which analysis
          is active, so the consequence is stated rather than confirmed away. */}
      {canAnalyze && !analyzeRecommended ? (
        <p className="text-support leading-6 text-cv-text-muted">
          ניתוח מחדש יוצר ניתוח חדש ונפרד לאותו תצלום משרה. הטיוטה הפעילה נשמרת כפי שהיא,
          אך תסומן כלא מעודכנת מולו.
        </p>
      ) : null}

      {canAnalyze ? (
        <ActionBar
          primary={
            <Button
              disabled={analyze.isPending}
              onClick={() => analyze.mutate()}
              variant={analyzeRecommended ? "primary" : "secondary"}
            >
              {analyze.isPending
                ? "מפעיל ניתוח…"
                : analyzeRecommended
                  ? "ניתוח המשרה"
                  : "ניתוח מחדש של המשרה"}
            </Button>
          }
        />
      ) : null}
    </div>
  );
};
