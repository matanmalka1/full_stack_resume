import { useMutation, useQueryClient } from "@tanstack/react-query";
import { SlidersHorizontal } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

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
import { cx } from "@/ui/cx";
import { surfaceClasses } from "@/ui/surface";
import { emphasisLabels, languageLabels, optionsFrom, profileLabels, trackLabels } from "../../model/analysisLabels";
import {
  type MatchingKey,
  type MatchingValues,
  changedKeys,
  createsAnalysis,
  matchingConsequence,
  matchingKeys,
  matchingOrigin,
  matchingSubmission,
  matchingValuesFrom,
} from "../../model/matchingConfiguration";

const fields: Record<
  MatchingKey,
  { cost: string; description: string; label: string; labels: Record<string, string> }
> = {
  track: {
    label: "מסלול",
    labels: trackLabels,
    description: "תחום המשרה - קובע אילו פרופילים ודגשים רלוונטיים.",
    cost: "שינוי יוצר ניתוח חדש",
  },
  profile: {
    label: "פרופיל",
    labels: profileLabels,
    description: "התפקיד הספציפי - קובע את מאגר העובדות ואת מבנה קורות החיים.",
    cost: "שינוי יוצר ניתוח חדש",
  },
  emphasis: {
    label: "דגש",
    labels: emphasisLabels,
    description: "מה להבליט - משנה את דירוג העובדות בתוך הפרופיל.",
    cost: "שינוי יוצר בחירת עובדות חדשה בלבד",
  },
  language: {
    label: "שפת קורות החיים",
    labels: languageLabels,
    description: "השפה שבה ייכתבו קורות החיים.",
    cost: "שינוי יוצר ניתוח חדש",
  },
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

  const canEdit = detail.available_actions.includes("edit_matching_configuration");
  const changes = current === null || values === null ? [] : changedKeys(current, values);
  const changed = changes.length > 0;

  const save = useMutation({
    mutationFn: async () => {
      if (!canEdit || current === null || values === null || detail.active_analysis_id == null || !changed) {
        throw new Error("matching configuration is not available for this context");
      }
      return applyAnalysisDecisions(
        detail.active_analysis_id,
        detail.application.id,
        matchingSubmission(current, values),
        detail.active_selection_plan_id ?? null,
      );
    },
    onSuccess: async (result) => {
      onSaved(result);
      await invalidateApplicationViews(queryClient, detail.application.id);
    },
  });

  const navigate = useNavigate();
  const [pendingHref, setPendingHref] = useState<string | null>(null);

  useEffect(() => {
    if (!changed) return;
    const handler = (event: BeforeUnloadEvent) => event.preventDefault();
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [changed]);

  useEffect(() => {
    if (!changed || save.isPending) return;
    const handler = (event: MouseEvent) => {
      const anchor = (event.target as Element).closest("a");
      const href = anchor?.getAttribute("href");
      if (href?.startsWith("/") && !href.startsWith("//")) {
        event.preventDefault();
        setPendingHref(href);
      }
    };
    document.addEventListener("click", handler, true);
    return () => document.removeEventListener("click", handler, true);
  }, [changed, save.isPending]);

  const update = <K extends MatchingKey>(key: K, value: MatchingValues[K]) => {
    save.reset();
    setValues((existing) => (existing === null ? existing : { ...existing, [key]: value }));
  };

  const lockedByOperation = detail.blocked_actions
    .find((blocked) => blocked.action === "edit_matching_configuration")
    ?.reasons.includes("MATCHING_CONTEXT_OPERATION_IN_PROGRESS");

  if (current === null || values === null) {
    return null;
  }

  return (
    <section
      aria-labelledby="matching-configuration-heading"
      className={surfaceClasses("flex flex-col gap-4 bg-cv-surface p-5")}
    >
      <div className="flex items-start gap-2.5 border-b border-cv-border pb-3">
        <span className="flex size-9 shrink-0 items-center justify-center rounded-control bg-cv-accent-soft text-cv-accent">
          <SlidersHorizontal aria-hidden="true" className="size-icon-md" />
        </span>
        <div className="min-w-0">
          <h2 className="text-body font-semibold text-cv-text" id="matching-configuration-heading">
            הגדרות ההתאמה
          </h2>
          <p className="mt-0.5 text-support text-cv-text-muted">
            על פיהן נבחרות העובדות ונבנים קורות החיים. הערכים הוצעו בניתוח, ואפשר לשנות כל אחד מהם.
          </p>
        </div>
      </div>

      {lockedByOperation ? (
        <Callout title="ההגדרות נעולות בזמן שינוי ההקשר" tone="warning">
          יש להמתין לסיום ניתוח המשרה או שינוי בחירת העובדות, ואז לפתוח את ההגדרות המעודכנות.
        </Callout>
      ) : null}

      <div className="flex flex-col gap-4">
        {matchingKeys.map((key) => {
          const field = fields[key];
          const isChanged = changes.includes(key);
          const origin = matchingOrigin(key, classification, detail);
          return (
            <div
              className={cx(
                "rounded-control border p-3 transition-colors",
                isChanged ? "border-cv-accent/40 bg-cv-accent-soft/40" : "border-cv-border",
              )}
              key={key}
            >
              <Field hint={field.description} label={field.label}>
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
              <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-caption">
                {isChanged ? (
                  <span className="font-semibold text-cv-accent">
                    במקום: {field.labels[current[key]] ?? current[key]} · {field.cost}
                  </span>
                ) : (
                  <span
                    className={cx(
                      "rounded-pill px-2 py-0.5 font-semibold",
                      origin === "decided" ? "bg-cv-info-soft text-cv-info" : "bg-cv-surface-muted text-cv-text-muted",
                    )}
                  >
                    {origin === "decided" ? "נקבע על ידך" : "הוצע בניתוח"}
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {changed ? (
        <Callout
          title={createsAnalysis(changes) ? "השמירה תריץ ניתוח מחדש" : "השמירה תבחר את העובדות מחדש"}
          tone={detail.active_working_draft_id != null ? "warning" : "info"}
        >
          {matchingConsequence(detail, createsAnalysis(changes))}
        </Callout>
      ) : null}

      {save.error === null ? null : (
        <ErrorCallout
          error={save.error}
          fallbackDetail="ההגדרות לא נשמרו. ייתכן שהניתוח או בחירת העובדות התחלפו; הערכים שבחרת נשארו בטופס כדי שאפשר יהיה להשוות ולנסות שוב לאחר רענון."
          fallbackTitle="הגדרות ההתאמה לא נשמרו"
        />
      )}

      <LiveRegion>{save.isPending ? "שומר את הגדרות ההתאמה…" : undefined}</LiveRegion>

      <div className="flex flex-wrap items-center gap-3">
        <Button
          disabled={!canEdit || !changed}
          onClick={() => save.mutate()}
          pending={save.isPending}
          pendingLabel="שומר…"
        >
          שמירת הגדרות ההתאמה
        </Button>
        {changed ? (
          <Button
            disabled={save.isPending}
            onClick={() => {
              save.reset();
              setValues(current);
            }}
            variant="ghost"
          >
            ביטול השינויים
          </Button>
        ) : null}
        {!canEdit && !lockedByOperation ? (
          <p className="text-caption text-cv-text-muted">לא ניתן לשנות את ההגדרות בשלב הנוכחי.</p>
        ) : null}
      </div>

      <Dialog
        footer={
          <>
            <Button onClick={() => setPendingHref(null)} variant="secondary">
              המשך בעריכה
            </Button>
            <Button
              onClick={() => {
                const href = pendingHref;
                setPendingHref(null);
                if (href !== null) navigate(href);
              }}
              variant="destructive"
            >
              יציאה בלי שמירה
            </Button>
          </>
        }
        headingId="matching-configuration-leave-heading"
        onClose={() => setPendingHref(null)}
        open={pendingHref !== null}
        title="לצאת בלי לשמור את הגדרות ההתאמה?"
      >
        <p dir="auto">השינויים במסלול, בפרופיל, בדגש או בשפת קורות החיים לא נשמרו ויאבדו אם תצא/י מהמסך עכשיו.</p>
      </Dialog>
    </section>
  );
};
