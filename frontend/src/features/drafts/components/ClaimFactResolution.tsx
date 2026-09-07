import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo } from "react";

import { applicationDetailQueryKey } from "@/api/applications";
import type { DraftClaim, WorkingDraft } from "@/api/contracts";
import {
  confirmAndUseFact,
  factDetailQueryKey,
  factHistoryQueryKey,
  factHistoryQueryOptions,
  factsQueryPrefix,
} from "@/api/facts";
import { workingDraftFactsQueryKey } from "@/api/drafts";
import { ErrorCallout } from "@/app/ErrorCallout";
import {
  emptyFactForm,
  FactCoreFields,
  FactEventHistory,
  FactProvenanceField,
  FactSourceField,
  FactTagsField,
  factLabelInLanguage,
  factStatusLabel,
  parseFactTags,
  useCaptureClaimFact,
  useFactDetail,
  type FactFormFields,
} from "@/features/facts";
import { useAppForm } from "@/forms/useAppForm";
import { Button } from "@/ui/Button";
import { Callout } from "@/ui/Callout";
import { Checkbox } from "@/ui/Checkbox";
import { QueryState } from "@/ui/QueryState";

interface ClaimFactResolutionProps {
  analysisId: string | null;
  applicationId: string;
  claim: DraftClaim;
  draft: WorkingDraft;
  language: string;
  profile: string | null;
  section: string;
}

/* Turning an unsupported line of the draft into a fact the CV is allowed to carry. The
   claim's own text is copied into the fact verbatim - this flow never rewords it - and
   the person supplies what it means and how it is attested. A fact captured here is
   still pending; the second step confirms it and puts it into a fresh selection plan. */
export const ClaimFactResolution = ({
  analysisId,
  applicationId,
  claim,
  draft,
  language,
  profile,
  section,
}: ClaimFactResolutionProps) => {
  const queryClient = useQueryClient();
  /* The claim's own text is the fact's meaning, and the claim under this panel can
     change. `values` keeps that field tracking the claim without an effect writing into
     state after the fact, and `keepDirtyValues` stops it overwriting anything typed. */
  const captureForm = useAppForm<FactFormFields>({
    values: emptyFactForm(profile, claim.text),
    resetOptions: { keepDirtyValues: true },
  });
  const confirmationForm = useAppForm<{ confirmed: boolean }>({ defaultValues: { confirmed: false } });

  const historyQuery = useQuery(factHistoryQueryOptions);
  /* A fact captured for this claim on an earlier visit is found in the lifecycle log
     rather than remembered locally, so reopening the panel resumes at the confirmation
     step instead of offering to capture the same claim twice. */
  const recoveredFactId = useMemo(
    () =>
      [...(historyQuery.data?.events ?? [])]
        .reverse()
        .find((event) => event.application_id === applicationId && event.claim_id === claim.claim_id)?.fact_id ?? null,
    [applicationId, claim.claim_id, historyQuery.data],
  );

  const capture = useCaptureClaimFact();
  const factId = capture.data?.fact.fact_id ?? recoveredFactId;
  const detailQuery = useFactDetail(factId);

  const useFact = useMutation({
    mutationFn: () => {
      if (factId === null || analysisId === null || profile === null) {
        throw new Error("Confirm and use requires the active analysis and Profile");
      }
      return confirmAndUseFact(factId, {
        application_id: applicationId,
        job_analysis_id: analysisId,
        profile,
        section,
        reason: "confirmed from the contextual draft claim flow",
      });
    },
    /* Confirming reaches past the fact store: it writes a new selection plan, so the
       application and the draft's own fact list are stale too. */
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: factsQueryPrefix });
      void queryClient.invalidateQueries({ queryKey: factHistoryQueryKey });
      if (factId !== null) {
        void queryClient.invalidateQueries({ queryKey: factDetailQueryKey(factId) });
      }
      void queryClient.invalidateQueries({ queryKey: applicationDetailQueryKey(applicationId) });
      void queryClient.invalidateQueries({ queryKey: workingDraftFactsQueryKey(draft.id) });
    },
  });

  const error = historyQuery.error ?? detailQuery.error ?? capture.error ?? useFact.error;
  const confirmed = confirmationForm.watch("confirmed");
  const captureFields = { errors: captureForm.formState.errors, register: captureForm.register };

  const submitCapture = (fields: FactFormFields) =>
    capture.mutate({
      application_id: applicationId,
      claim_id: claim.claim_id,
      source: fields.source,
      meaning: fields.meaning.trim(),
      tags: parseFactTags(fields.tags),
      provenance: fields.provenance.trim(),
      reason: "captured from the contextual draft claim flow",
      ...(language === "he" ? { english: fields.english.trim() } : {}),
    });

  return (
    <details className="mt-3 rounded-control border border-cv-border bg-cv-surface-muted p-4">
      <summary className="cursor-pointer font-semibold text-cv-text">הפיכת הטקסט לעובדה מאושרת</summary>
      {error === null ? null : (
        <ErrorCallout
          className="mt-4"
          error={error}
          fallbackDetail="מחזור החיים לא השתנה ואפשר לנסות שוב."
          fallbackTitle="לא ניתן לעדכן את העובדה"
        />
      )}

      {factId === null ? (
        <form className="mt-4 flex flex-col gap-3" onSubmit={captureForm.handleSubmit(submitCapture)}>
          <Callout title="הניסוח נשמר בדיוק" tone="neutral">
            הטקסט של השורה יועתק כפי שהוא. השדות הבאים מתארים את משמעותו ומקורו ואינם נוצרים באמצעות AI.
          </Callout>
          <FactSourceField register={captureForm.register} />
          <FactCoreFields
            {...captureFields}
            englishHint="הטקסט העברי נשאר הניסוח המדויק של השורה; נדרש גם ניסוח אנגלי מפורש לאחסון ניטרלי לשפה."
            showEnglish={language === "he"}
          />
          <FactTagsField {...captureFields} />
          <FactProvenanceField {...captureFields} />
          <Button pending={capture.isPending} pendingLabel="יוצר עובדה…" type="submit">
            יצירת עובדה ממתינה
          </Button>
        </form>
      ) : detailQuery.data === undefined ? (
        <QueryState className="mt-4 text-support" loading loadingLabel="טוען את העובדה…" />
      ) : useFact.isSuccess ? (
        <Callout className="mt-4" role="status" title="העובדה אושרה ונבחרה" tone="success">
          נוצרה תוכנית בחירה חדשה. הטיוטה הנוכחית נשמרה, ומסך המועמדות יציע לבנות אותה מחדש מהתוכנית החדשה.
        </Callout>
      ) : (
        <div className="mt-4 flex flex-col gap-4">
          <div>
            <p className="font-semibold text-cv-text" dir="auto">
              {factLabelInLanguage(detailQuery.data.fact, language)}
            </p>
            <p className="text-support text-cv-text-muted">מצב: {factStatusLabel(detailQuery.data.fact.status)}</p>
          </div>
          <FactEventHistory events={detailQuery.data.events} />
          {analysisId === null || profile === null ? (
            <Callout title="נדרש ניתוח פעיל" tone="blocker">
              אי אפשר ליצור תוכנית בחירה חדשה בלי ניתוח ופרופיל פעילים.
            </Callout>
          ) : (
            <form className="flex flex-col gap-3" onSubmit={confirmationForm.handleSubmit(() => useFact.mutate())}>
              <Checkbox {...confirmationForm.register("confirmed")}>
                בדקתי את הניסוח, המשמעות, התגיות והמקור ואני מאשר לקדם, לצרף ולבחור את העובדה
              </Checkbox>
              <Button disabled={!confirmed} pending={useFact.isPending} pendingLabel="מאשר ומשתמש…" type="submit">
                אישור העובדה ושימוש בה
              </Button>
            </form>
          )}
        </div>
      )}
    </details>
  );
};
