import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type ReactNode, useEffect, useRef } from "react";

import { invalidateApplicationViews } from "../../api/applications";
import type { WorkingDraft } from "../../api/contracts";
import { validateWorkingDraft, validationRunQueryOptions } from "../../api/validation";
import { briefServerFailureDetail, ErrorCallout } from "../../app/ErrorCallout";
import { ActionBar } from "../../ui/ActionBar";
import { Button } from "../../ui/Button";
import { Callout } from "../../ui/Callout";
import { LiveRegion } from "../../ui/LiveRegion";
import { ValidationReportView } from "../revision/ValidationReportView";

interface DraftValidationPanelProps {
  applicationId: string;
  /* The approval control, rendered inside this panel's own footer. Approval is the one
     thing a passing run is for, and it used to sit in a second surface below - two cards
     saying one thing, the lower one repeating in a sentence what the upper one had just
     reported. */
  approval: ReactNode;
  draft: WorkingDraft | undefined;
  /* Approval is the editor's own dialog, so the panel reports the exact passing run
     upward rather than linking to a screen for it. */
  onExactPassingRun: (runId: string | null) => void;
  /* Set when an approval was refused as stale: the panel says so instead of the user
     arriving at a validation screen with an unexplained warning. */
  stale: boolean;
}

/* A.4 frame 5, as a panel of the editor rather than a screen of its own. The draft it
   validates is the one in the editor beside it, so making the user leave the editor to
   read the result - and come back to fix it - was the trip this removes. Every command,
   key, and stale path is the one the standalone screen used. */
export const DraftValidationPanel = ({
  applicationId,
  approval,
  draft,
  onExactPassingRun,
  stale,
}: DraftValidationPanelProps) => {
  const queryClient = useQueryClient();
  const summaryRef = useRef<HTMLHeadingElement>(null);

  const runId = draft?.latest_validation_run_id ?? null;
  const runQuery = useQuery({
    ...validationRunQueryOptions(runId ?? ""),
    enabled: runId !== null,
  });

  const validation = useMutation({
    mutationFn: async () => {
      if (draft === undefined) throw new Error("Validation was offered before the draft loaded");
      return validateWorkingDraft(draft.id, draft.edit_version);
    },
    onSuccess: () => {
      void invalidateApplicationViews(queryClient, applicationId);
    },
  });

  const run = validation.data ?? runQuery.data;
  /* §14: approval names an exact version. A run that describes any other draft, edit
     version, or content hash is evidence about a version that no longer exists. */
  const exactPassingRun =
    run?.passed === true &&
    draft !== undefined &&
    run.application_id === applicationId &&
    run.working_draft_id === draft.id &&
    run.edit_version === draft.edit_version &&
    run.content_hash === draft.content_hash;

  useEffect(() => {
    if (validation.data !== undefined) summaryRef.current?.focus();
  }, [validation.data]);

  /* The dialog upstream may only open for a run this panel has confirmed exact. */
  useEffect(() => {
    onExactPassingRun(exactPassingRun && run !== undefined ? run.validation_run_id : null);
  }, [exactPassingRun, onExactPassingRun, run]);

  const error = runQuery.error ?? validation.error;

  return (
    <section aria-labelledby="validation-summary" className="flex flex-col gap-3 border-t border-cv-border pt-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-heading-sm font-bold text-cv-text" id="validation-summary" ref={summaryRef} tabIndex={-1}>
          {run === undefined ? "אימות הטיוטה" : run.passed ? "הטיוטה עברה אימות" : "הטיוטה לא עברה אימות"}
        </h2>
        <Button
          disabled={draft === undefined}
          onClick={() => validation.mutate()}
          pending={validation.isPending}
          pendingLabel="מאמת…"
          variant="secondary"
        >
          {run === undefined ? "אימות הטיוטה" : "אימות מחדש"}
        </Button>
      </div>

      {stale ? (
        <Callout title="הטיוטה השתנתה מאז האימות" tone="warning">
          יש להריץ אימות חדש לגרסה הנוכחית. לא הופעל אישור ולא בוצע אימות מחדש אוטומטי.
        </Callout>
      ) : null}

      {error === null ? null : (
        <ErrorCallout
          error={error}
          fallbackDetail={briefServerFailureDetail}
          fallbackTitle="לא ניתן להשלים את האימות"
        />
      )}

      {run === undefined ? (
        <p className="text-support leading-6 text-cv-text-muted">
          האימות בודק את גרסת הטיוטה המדויקת שמוצגת כאן, לפני אישור.
        </p>
      ) : (
        <ValidationReportView report={run.report} />
      )}

      <ActionBar className="border-t border-cv-border pt-3" primary={approval} />

      <LiveRegion>
        {validation.data === undefined
          ? ""
          : validation.data.passed
            ? "האימות הושלם בהצלחה."
            : "האימות הושלם והטיוטה לא עברה."}
      </LiveRegion>
    </section>
  );
};
