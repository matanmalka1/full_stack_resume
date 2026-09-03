import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo } from "react";

import { applicationDetailQueryKey } from "../../api/applications";
import type { DraftClaim, WorkingDraft } from "../../api/contracts";
import {
  captureClaimFact,
  confirmAndUseFact,
  factDetailQueryKey,
  factDetailQueryOptions,
  factHistoryQueryKey,
  factHistoryQueryOptions,
  factsQueryPrefix,
} from "../../api/facts";
import { workingDraftFactsQueryKey } from "../../api/drafts";
import { ErrorCallout } from "../../app/ErrorCallout";
import { useAppForm } from "../../forms/useAppForm";
import { Button } from "../../ui/Button";
import { Callout } from "../../ui/Callout";
import { Checkbox } from "../../ui/Checkbox";
import { QueryState } from "../../ui/QueryState";
import { FactEventHistory } from "../facts/FactEventHistory";
import { defaultFactSource, FactFields, type FactFormFields, parseFactTags } from "../facts/FactFields";
import { factStatusLabel } from "../facts/factLabels";

interface ClaimFactResolutionProps {
  analysisId: string | null;
  applicationId: string;
  claim: DraftClaim;
  draft: WorkingDraft;
  language: string;
  profile: string | null;
  section: string;
}

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
  const captureForm = useAppForm<FactFormFields>({
    defaultValues: {
      english: "",
      hebrew: "",
      meaning: claim.text,
      provenance: "",
      source: defaultFactSource(profile),
      style: "bullet",
      tags: "",
    },
  });
  const confirmationForm = useAppForm<{ confirmed: boolean }>({ defaultValues: { confirmed: false } });
  const { setValue: setCaptureValue } = captureForm;
  const historyQuery = useQuery(factHistoryQueryOptions);
  const recoveredFactId = useMemo(
    () =>
      [...(historyQuery.data?.events ?? [])]
        .reverse()
        .find((event) => event.application_id === applicationId && event.claim_id === claim.claim_id)?.fact_id ?? null,
    [applicationId, claim.claim_id, historyQuery.data],
  );

  const refreshFacts = (id?: string) => {
    void queryClient.invalidateQueries({ queryKey: factsQueryPrefix });
    void queryClient.invalidateQueries({ queryKey: factHistoryQueryKey });
    if (id !== undefined) {
      void queryClient.invalidateQueries({ queryKey: factDetailQueryKey(id) });
    }
  };
  const capture = useMutation({
    mutationFn: (fields: FactFormFields) =>
      captureClaimFact({
        application_id: applicationId,
        claim_id: claim.claim_id,
        source: fields.source,
        meaning: fields.meaning.trim(),
        tags: parseFactTags(fields.tags),
        provenance: fields.provenance.trim(),
        reason: "captured from the contextual draft claim flow",
        ...(language === "he" ? { english: fields.english.trim() } : {}),
      }),
    onSuccess: (result) => {
      refreshFacts(result.fact.fact_id);
    },
  });
  const resolvedFactId = capture.data?.fact.fact_id ?? recoveredFactId;
  const detailQuery = useQuery({
    ...factDetailQueryOptions(resolvedFactId ?? ""),
    enabled: resolvedFactId !== null,
  });

  useEffect(() => setCaptureValue("meaning", claim.text), [claim.text, setCaptureValue]);

  const useFact = useMutation({
    mutationFn: () => {
      if (resolvedFactId === null || analysisId === null || profile === null) {
        throw new Error("Confirm and use requires the active analysis and Profile");
      }
      return confirmAndUseFact(resolvedFactId, {
        application_id: applicationId,
        job_analysis_id: analysisId,
        profile,
        section,
        reason: "confirmed from the contextual draft claim flow",
      });
    },
    onSuccess: () => {
      refreshFacts(resolvedFactId ?? undefined);
      void queryClient.invalidateQueries({ queryKey: applicationDetailQueryKey(applicationId) });
      void queryClient.invalidateQueries({ queryKey: workingDraftFactsQueryKey(draft.id) });
    },
  });
  const error = historyQuery.error ?? detailQuery.error ?? capture.error ?? useFact.error;
  const confirmed = confirmationForm.watch("confirmed");

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
      {resolvedFactId === null ? (
        <form
          className="mt-4 flex flex-col gap-3"
          onSubmit={captureForm.handleSubmit((fields) => capture.mutate(fields))}
        >
          <Callout title="הניסוח נשמר בדיוק" tone="neutral">
            הטקסט של השורה יועתק כפי שהוא. השדות הבאים מתארים את משמעותו ומקורו ואינם נוצרים באמצעות AI.
          </Callout>
          <FactFields
            englishHint="הטקסט העברי נשאר הניסוח המדויק של השורה; נדרש גם ניסוח אנגלי מפורש לאחסון ניטרלי לשפה."
            errors={captureForm.formState.errors}
            register={captureForm.register}
            showEnglish={language === "he"}
          />
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
              {detailQuery.data.fact.renderings[language] ??
                detailQuery.data.fact.renderings.en ??
                detailQuery.data.fact.meaning}
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
