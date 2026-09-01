import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";

import { applicationDetailQueryKey } from "../../api/applications";
import type { CaptureClaimFactRequest, DraftClaim, WorkingDraft } from "../../api/contracts";
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
import { Button } from "../../ui/Button";
import { Callout } from "../../ui/Callout";
import { Checkbox } from "../../ui/Checkbox";
import { Field } from "../../ui/Field";
import { Select } from "../../ui/Select";
import { TextArea, TextInput } from "../../ui/TextInput";
import { QueryState } from "../../ui/QueryState";

type FactSource = CaptureClaimFactRequest["source"];

const sourceLabels: Record<FactSource, string> = {
  "common.md": "עובדות משותפות",
  "sales.md": "ניסיון במכירות",
  "development.md": "ניסיון בפיתוח",
  "situational_skills.md": "כישורים מצביים",
};

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
  const historyQuery = useQuery(factHistoryQueryOptions);
  const recoveredFactId = useMemo(
    () =>
      [...(historyQuery.data?.events ?? [])]
        .reverse()
        .find((event) => event.application_id === applicationId && event.claim_id === claim.claim_id)?.fact_id ?? null,
    [applicationId, claim.claim_id, historyQuery.data],
  );
  const [capturedFactId, setCapturedFactId] = useState<string | null>(null);
  const factId = capturedFactId ?? recoveredFactId;
  const detailQuery = useQuery({
    ...factDetailQueryOptions(factId ?? ""),
    enabled: factId !== null,
  });
  const [source, setSource] = useState<FactSource>(profile === "development" ? "development.md" : "sales.md");
  const [meaning, setMeaning] = useState(claim.text);
  const [tags, setTags] = useState("");
  const [provenance, setProvenance] = useState("");
  const [english, setEnglish] = useState("");
  const [confirmed, setConfirmed] = useState(false);

  useEffect(() => setMeaning(claim.text), [claim.text]);

  const refreshFacts = (id?: string) => {
    void queryClient.invalidateQueries({ queryKey: factsQueryPrefix });
    void queryClient.invalidateQueries({ queryKey: factHistoryQueryKey });
    if (id !== undefined) {
      void queryClient.invalidateQueries({ queryKey: factDetailQueryKey(id) });
    }
  };
  const capture = useMutation({
    mutationFn: () =>
      captureClaimFact({
        application_id: applicationId,
        claim_id: claim.claim_id,
        source,
        meaning: meaning.trim(),
        tags: tags
          .split(",")
          .map((tag) => tag.trim())
          .filter(Boolean),
        provenance: provenance.trim(),
        reason: "captured from the contextual draft claim flow",
        ...(language === "he" ? { english: english.trim() } : {}),
      }),
    onSuccess: (result) => {
      setCapturedFactId(result.fact.fact_id);
      refreshFacts(result.fact.fact_id);
    },
  });
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
    onSuccess: () => {
      refreshFacts(factId ?? undefined);
      void queryClient.invalidateQueries({ queryKey: applicationDetailQueryKey(applicationId) });
      void queryClient.invalidateQueries({ queryKey: workingDraftFactsQueryKey(draft.id) });
    },
  });
  const error = historyQuery.error ?? detailQuery.error ?? capture.error ?? useFact.error;
  const tagsPresent = tags.split(",").some((tag) => tag.trim() !== "");
  const canCapture =
    meaning.trim() !== "" && provenance.trim() !== "" && tagsPresent && (language !== "he" || english.trim() !== "");

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
        <form
          className="mt-4 flex flex-col gap-3"
          onSubmit={(event) => {
            event.preventDefault();
            capture.mutate();
          }}
        >
          <Callout title="הניסוח נשמר בדיוק" tone="neutral">
            הטקסט של השורה יועתק כפי שהוא. השדות הבאים מתארים את משמעותו ומקורו ואינם נוצרים באמצעות AI.
          </Callout>
          <Field label="מקור הידע">
            {(control) => (
              <Select {...control} onChange={(event) => setSource(event.target.value as FactSource)} value={source}>
                {Object.entries(sourceLabels).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field label="משמעות העובדה">
            {(control) => (
              <TextArea
                {...control}
                dir="auto"
                onChange={(event) => setMeaning(event.target.value)}
                required
                value={meaning}
              />
            )}
          </Field>
          {language !== "he" ? null : (
            <Field
              hint="הטקסט העברי נשאר הניסוח המדויק של השורה; נדרש גם ניסוח אנגלי מפורש לאחסון ניטרלי לשפה."
              label="ניסוח באנגלית"
            >
              {(control) => (
                <TextArea
                  {...control}
                  dir="ltr"
                  onChange={(event) => setEnglish(event.target.value)}
                  required
                  value={english}
                />
              )}
            </Field>
          )}
          <Field hint="יש להפריד תגיות בפסיקים." label="תגיות">
            {(control) => (
              <TextInput {...control} onChange={(event) => setTags(event.target.value)} required value={tags} />
            )}
          </Field>
          <Field label="מקור ואימות העובדה">
            {(control) => (
              <TextArea
                {...control}
                dir="auto"
                onChange={(event) => setProvenance(event.target.value)}
                required
                value={provenance}
              />
            )}
          </Field>
          <Button disabled={!canCapture} pending={capture.isPending} pendingLabel="יוצר עובדה…" type="submit">
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
            <p className="text-support text-cv-text-muted">
              מצב: {detailQuery.data.fact.status === "pending" ? "ממתינה" : detailQuery.data.fact.status}
            </p>
          </div>
          <ol className="flex flex-col gap-2">
            {detailQuery.data.events.map((event) => (
              <li className="border-s-2 border-cv-border ps-3 text-support text-cv-text-muted" key={event.id}>
                {event.from_status == null ? "נוצרה כממתינה" : `${event.from_status} ← ${event.to_status}`}
              </li>
            ))}
          </ol>
          {analysisId === null || profile === null ? (
            <Callout title="נדרש ניתוח פעיל" tone="blocker">
              אי אפשר ליצור תוכנית בחירה חדשה בלי ניתוח ופרופיל פעילים.
            </Callout>
          ) : (
            <>
              <Checkbox checked={confirmed} onChange={(event) => setConfirmed(event.currentTarget.checked)}>
                בדקתי את הניסוח, המשמעות, התגיות והמקור ואני מאשר לקדם, לצרף ולבחור את העובדה
              </Checkbox>
              <Button
                disabled={!confirmed}
                onClick={() => useFact.mutate()}
                pending={useFact.isPending}
                pendingLabel="מאשר ומשתמש…"
              >
                אישור העובדה ושימוש בה
              </Button>
            </>
          )}
        </div>
      )}
    </details>
  );
};
