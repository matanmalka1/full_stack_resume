import { useMutation, useQueryClient } from "@tanstack/react-query";
import { SlidersHorizontal } from "lucide-react";
import { useMemo, useState } from "react";

import { applyAnalysisDecisions, type Classification } from "@/api/analyses";
import { invalidateApplicationViews } from "@/api/applications";
import type { ApplicationDetail } from "@/api/contracts";
import { Button } from "@/ui/Button";
import { Callout } from "@/ui/Callout";
import { Dialog } from "@/ui/Dialog";
import { ErrorCallout } from "@/ui/ErrorCallout";
import { Field } from "@/ui/Field";
import { LiveRegion } from "@/ui/LiveRegion";
import { Select } from "@/ui/Select";
import { emphasisLabels, languageLabels, optionsFrom, profileLabels, trackLabels } from "../../model/analysisLabels";
import {
  type MatchingKey,
  type MatchingValues,
  changedKeys,
  matchingConsequence,
  matchingKeys,
  matchingOrigin,
  matchingSubmission,
  matchingValuesFrom,
} from "../../model/matchingConfiguration";

const fields: Record<MatchingKey, { cost: string; label: string; labels: Record<string, string> }> = {
  track: { label: "מסלול", labels: trackLabels, cost: "ניתוח חדש" },
  profile: { label: "פרופיל", labels: profileLabels, cost: "ניתוח חדש" },
  emphasis: { label: "דגש", labels: emphasisLabels, cost: "בחירת עובדות חדשה" },
  language: { label: "שפת קורות החיים", labels: languageLabels, cost: "ניתוח חדש" },
};

export const MatchingConfigurationEditor = ({
  classification,
  detail,
  onSaved,
}: {
  classification: Classification;
  detail: ApplicationDetail;
  onSaved: (result: Awaited<ReturnType<typeof applyAnalysisDecisions>>) => void;
}) => {
  const queryClient = useQueryClient();
  const current = useMemo(() => matchingValuesFrom(classification), [classification]);
  const [values, setValues] = useState<MatchingValues | null>(current);
  const [open, setOpen] = useState(false);

  const canEdit = detail.available_actions.includes("edit_matching_configuration");
  const changes = current === null || values === null ? [] : changedKeys(current, values);
  const changed = changes.length > 0;

  const save = useMutation({
    mutationFn: async () => {
      /* The analysis the form shows is the latest one of the active posting
         (`classificationFromAnalysis`), so that is the one the decision addresses. */
      if (!canEdit || current === null || values === null || detail.latest_analysis_id == null || !changed) {
        throw new Error("matching configuration is not available for this context");
      }
      return applyAnalysisDecisions(
        detail.latest_analysis_id,
        detail.application.id,
        detail.document_hash ?? null,
        matchingSubmission(current, values),
      );
    },
    onSuccess: async (result) => {
      setOpen(false);
      onSaved(result);
      await invalidateApplicationViews(queryClient, detail.application.id);
    },
  });

  const update = <K extends MatchingKey>(key: K, value: MatchingValues[K]) => {
    save.reset();
    setValues((existing) => (existing === null ? existing : { ...existing, [key]: value }));
  };

  /* Written content is what a change can affect, so it is what raises the tone. */
  const hasContent =
    detail.preparation_state === "draft_in_progress" ||
    detail.preparation_state === "approved" ||
    detail.preparation_state === "ready";

  const lockedByOperation = detail.blocked_actions
    .find((blocked) => blocked.action === "edit_matching_configuration")
    ?.reasons.includes("MATCHING_CONTEXT_OPERATION_IN_PROGRESS");

  if (current === null || values === null) {
    return null;
  }

  /* Closing is a deliberate cancel (Escape, the close control, or "ביטול"): the dialog
     discards unsaved choices rather than carrying them to the next opening. The backdrop
     click that `Dialog` refuses while fields are edited is the accidental one. */
  const close = () => {
    save.reset();
    setValues(current);
    setOpen(false);
  };

  return (
    <div className="mt-3 flex flex-wrap items-center justify-between gap-3 rounded-control bg-cv-surface-muted px-3 py-2">
      <dl aria-label="הגדרות ההתאמה הנוכחיות" className="flex flex-wrap gap-x-4 gap-y-1 text-caption">
        {matchingKeys.map((key) => (
          <div className="flex gap-1" key={key}>
            <dt className="text-cv-text-muted">{fields[key].label}:</dt>
            <dd className="font-semibold text-cv-text">{fields[key].labels[current[key]] ?? current[key]}</dd>
          </div>
        ))}
      </dl>

      <Button onClick={() => setOpen(true)} variant="secondary">
        <SlidersHorizontal aria-hidden="true" className="size-icon-sm shrink-0" />
        הגדרות ההתאמה
      </Button>

      <Dialog
        description="שינוי מסלול, פרופיל או שפה יוצר ניתוח חדש; שינוי דגש בוחר את העובדות מחדש."
        dismissible={!save.isPending}
        footer={
          <>
            <Button disabled={save.isPending} onClick={close} variant="secondary">
              ביטול
            </Button>
            <Button
              disabled={!canEdit || !changed}
              onClick={() => save.mutate()}
              pending={save.isPending}
              pendingLabel="שומר…"
            >
              שמירת הגדרות ההתאמה
            </Button>
          </>
        }
        headingId="matching-configuration-heading"
        onClose={close}
        open={open}
        title="הגדרות ההתאמה"
      >
        <div className="flex flex-col gap-4">
          {lockedByOperation ? (
            <Callout title="ההגדרות נעולות בזמן שינוי ההקשר" tone="warning">
              יש להמתין לסיום ניתוח המשרה, ואז לפתוח את ההגדרות המעודכנות.
            </Callout>
          ) : null}

          {!canEdit && !lockedByOperation ? (
            <p className="text-caption text-cv-text-muted">לא ניתן לשנות את ההגדרות בשלב הנוכחי.</p>
          ) : null}

          <div className="grid gap-x-4 gap-y-3 sm:grid-cols-2">
            {matchingKeys.map((key) => {
              const field = fields[key];
              const isChanged = changes.includes(key);
              const origin = matchingOrigin(key, classification);
              return (
                <Field
                  hint={
                    <span className={isChanged ? "font-semibold text-cv-accent" : undefined}>
                      {isChanged
                        ? `במקום ${field.labels[current[key]] ?? current[key]} · ${field.cost}`
                        : origin === "decided"
                          ? "נקבע על ידך"
                          : "הוצע בניתוח"}
                    </span>
                  }
                  key={key}
                  label={field.label}
                >
                  {(control) => (
                    <Select
                      {...control}
                      disabled={!canEdit || save.isPending}
                      onChange={(event) => update(key, event.target.value as MatchingValues[typeof key])}
                      value={values[key]}
                    >
                      {optionsFrom(field.labels).map(([option, optionLabel]) => (
                        <option key={option} value={option}>
                          {optionLabel}
                        </option>
                      ))}
                    </Select>
                  )}
                </Field>
              );
            })}
          </div>

          {changed ? (
            <Callout title="השמירה תיצור ניתוח חדש" tone={hasContent ? "warning" : "info"}>
              {matchingConsequence(detail)}
            </Callout>
          ) : null}

          {save.error === null ? null : (
            <ErrorCallout
              error={save.error}
              fallbackDetail="הבחירות שלך נשארו בטופס. אפשר לרענן את העמוד ולנסות שוב."
              title="הגדרות ההתאמה לא נשמרו"
            />
          )}

          <LiveRegion>{save.isPending ? "שומר את הגדרות ההתאמה…" : undefined}</LiveRegion>
        </div>
      </Dialog>
    </div>
  );
};
