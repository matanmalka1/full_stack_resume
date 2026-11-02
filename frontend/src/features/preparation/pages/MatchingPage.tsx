import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Info } from "lucide-react";
import { useId, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { type Classification, applyAnalysisDecisions, classificationFromAnalysis } from "@/api/analyses";
import { invalidateApplicationViews, watchedApplicationDetailQueryOptions } from "@/api/applications";
import type { ApplicationDetail } from "@/api/contracts";
import { useIsPhone } from "@/features/operations";
import { routePaths } from "@/navigation/routePaths";
import { useRequiredParam } from "@/navigation/useRequiredParam";
import { Button, buttonClasses } from "@/ui/Button";
import { Callout } from "@/ui/Callout";
import { ErrorCallout } from "@/ui/ErrorCallout";
import { LiveRegion } from "@/ui/LiveRegion";
import { PhoneActionBar } from "@/ui/PhoneActionBar";
import { QueryState } from "@/ui/QueryState";
import { SegmentedControl } from "@/ui/SegmentedControl";
import { Select } from "@/ui/Select";
import { Skeleton } from "@/ui/Skeleton";
import { cardClasses } from "@/ui/surface";
import { StepFrame } from "../components/StepFrame";
import {
  classificationFieldLabels,
  emphasisLabels,
  languageLabels,
  optionsFrom,
  profileLabels,
  trackLabels,
} from "../model/analysisLabels";
import {
  type MatchingValues,
  changedKeys,
  matchingConsequence,
  matchingOrigin,
  matchingSubmission,
  matchingValuesFrom,
} from "../model/matchingConfiguration";

type SelectKey = "track" | "profile" | "emphasis";

const selects: { key: SelectKey; labels: Record<string, string> }[] = [
  { key: "track", labels: trackLabels },
  { key: "profile", labels: profileLabels },
  { key: "emphasis", labels: emphasisLabels },
];

/* Where a field's value came from, at the end of its label row: the analysis proposed it,
   or the reader decided it - the decided one drawn as a tag, since it is the exception. */
const OriginTag = ({ changed, decided }: { changed: boolean; decided: boolean }) =>
  changed ? (
    <span className="text-caption font-bold text-cv-text">שונה · יישמר</span>
  ) : decided ? (
    <span className="rounded-pill bg-cv-surface-muted px-2 py-0.5 text-caption font-bold text-cv-text">
      נקבע על ידך
    </span>
  ) : (
    <span className="text-caption text-cv-text-muted">הוצע בניתוח</span>
  );

const MatchingForm = ({ classification, detail }: { classification: Classification; detail: ApplicationDetail }) => {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const isPhone = useIsPhone();
  const id = useId();
  const current = useMemo(() => matchingValuesFrom(classification), [classification]);
  const [values, setValues] = useState<MatchingValues | null>(current);
  const analysisPath = routePaths.analysis(detail.application.id);

  const canEdit = detail.available_actions.includes("edit_matching_configuration");
  const changes = current === null || values === null ? [] : changedKeys(current, values);
  const lockedByOperation = detail.blocked_actions
    .find((blocked) => blocked.action === "edit_matching_configuration")
    ?.reasons.includes("MATCHING_CONTEXT_OPERATION_IN_PROGRESS");

  const save = useMutation({
    mutationFn: async () => {
      /* The form shows the latest analysis of the active posting, so that is the one the
         decision addresses. */
      if (
        !canEdit ||
        current === null ||
        values === null ||
        detail.latest_analysis_id == null ||
        changes.length === 0
      ) {
        throw new Error("matching configuration is not available for this context");
      }
      return applyAnalysisDecisions(
        detail.latest_analysis_id,
        detail.application.id,
        detail.document_hash ?? null,
        matchingSubmission(current, values),
      );
    },
    onSuccess: async () => {
      await invalidateApplicationViews(queryClient, detail.application.id);
      void navigate(analysisPath);
    },
  });

  if (current === null || values === null) {
    return (
      <Callout title="אין הגדרות התאמה לשנות" tone="neutral">
        הניתוח הנוכחי לא קבע מסלול, פרופיל, דגש ושפה, ולכן אין כאן מה לשנות. ניתוח מחדש יקבע אותם.
      </Callout>
    );
  }

  const update = <K extends keyof MatchingValues>(key: K, value: MatchingValues[K]) => {
    save.reset();
    setValues((existing) => (existing === null ? existing : { ...existing, [key]: value }));
  };
  const disabled = !canEdit || save.isPending;

  const commands = (
    <>
      <Link className={buttonClasses("secondary", "max-lg:flex-1")} to={analysisPath}>
        ביטול
      </Link>
      <Button
        className="shadow-action max-lg:flex-1"
        disabled={!canEdit || changes.length === 0}
        onClick={() => save.mutate()}
        pending={save.isPending}
        pendingLabel="שומר…"
        size="default"
      >
        שמירה
      </Button>
    </>
  );

  return (
    <div className="flex flex-col gap-5 max-lg:gap-4">
      {lockedByOperation ? (
        <Callout title="ההגדרות נעולות בזמן שינוי ההקשר" tone="warning">
          יש להמתין לסיום ניתוח המשרה, ואז לפתוח את ההגדרות המעודכנות.
        </Callout>
      ) : !canEdit ? (
        <p className="text-support text-cv-text-muted">לא ניתן לשנות את ההגדרות בשלב הנוכחי.</p>
      ) : null}

      <div className={cardClasses("grid gap-x-5 gap-y-6 p-6 lg:grid-cols-3 max-lg:gap-0 max-lg:p-0")}>
        {selects.map(({ key, labels }) => (
          <div className="flex flex-col gap-2 max-lg:border-b max-lg:border-cv-canvas max-lg:p-3.5" key={key}>
            <div className="flex items-center justify-between gap-2">
              <label className="text-label font-bold text-cv-text" htmlFor={`${id}-${key}`}>
                {classificationFieldLabels[key]}
              </label>
              <OriginTag changed={changes.includes(key)} decided={matchingOrigin(key, classification) === "decided"} />
            </div>
            <Select
              disabled={disabled}
              id={`${id}-${key}`}
              onChange={(event) => update(key, event.target.value as MatchingValues[typeof key])}
              value={values[key]}
            >
              {optionsFrom(labels).map(([option, optionLabel]) => (
                <option key={option} value={option}>
                  {optionLabel}
                </option>
              ))}
            </Select>
          </div>
        ))}
        <div className="max-lg:p-3.5">
          <SegmentedControl
            disabled={disabled}
            label={classificationFieldLabels.language}
            onChange={(language) => update("language", language)}
            options={optionsFrom(languageLabels).map(([value, label]) => ({ label, value }))}
            value={values.language}
          />
        </div>
      </div>

      <div className="flex items-start gap-2.5 rounded-surface bg-cv-surface-muted px-5 py-4 max-lg:px-3.5">
        <Info aria-hidden="true" className="mt-0.5 size-icon-lg shrink-0 text-cv-text" />
        <div className="text-support leading-relaxed">
          <p className="text-label font-bold text-cv-text">השמירה תיצור ניתוח חדש</p>
          <p className="text-cv-text-muted">
            {changes.length === 0
              ? "שינוי מסלול, פרופיל או שפה יוצר ניתוח חדש; שינוי דגש בוחר את העובדות מחדש."
              : matchingConsequence(detail)}
          </p>
        </div>
      </div>

      {save.error === null ? null : (
        <ErrorCallout
          error={save.error}
          fallbackDetail="הבחירות שלך נשארו בטופס. אפשר לרענן את העמוד ולנסות שוב."
          title="הגדרות ההתאמה לא נשמרו"
        />
      )}
      <LiveRegion>{save.isPending ? "שומר את הגדרות ההתאמה…" : undefined}</LiveRegion>

      {isPhone ? (
        <PhoneActionBar>{commands}</PhoneActionBar>
      ) : (
        <div className="flex justify-end gap-2.5">{commands}</div>
      )}
    </div>
  );
};

/* The matching settings of the analysis in force: track, profile, emphasis and the CV's
   language, each marked by where its value came from. Saving is a decision on the
   analysis - every change creates a new one - so the screen says so before the press. */
export const MatchingPage = () => {
  const applicationId = useRequiredParam("applicationId");
  const query = useQuery(watchedApplicationDetailQueryOptions(applicationId));
  const detail = query.data;
  const classification = detail === undefined ? null : classificationFromAnalysis(detail);

  return (
    <StepFrame
      applicationId={applicationId}
      back={{ label: "חזרה לניתוח המשרה", to: routePaths.analysis(applicationId) }}
      detail={detail}
      measure="form"
      phoneHeading
      rail="phone"
      stage="analysis"
      subtitle={
        detail === undefined ? (
          <Skeleton className="inline-block w-48 align-middle" />
        ) : (
          `${detail.application.target_role} · ${detail.application.company} · ניתוח והתאמה, 2 מתוך 4`
        )
      }
      title="הגדרות ההתאמה"
    >
      <QueryState
        error={query.error}
        errorTitle="לא ניתן לטעון את הגדרות ההתאמה"
        loading={detail === undefined}
        onRetry={() => void query.refetch()}
      >
        {detail === undefined ? null : classification === null ? (
          <Callout title="אין ניתוח פעיל" tone="neutral">
            הגדרות ההתאמה נקבעות בניתוח המשרה. אחרי שהניתוח יסתיים אפשר יהיה לשנות אותן מכאן.
          </Callout>
        ) : (
          /* A new analysis or document remounts the form so stale choices are never
             submitted. */
          <MatchingForm
            classification={classification}
            detail={detail}
            key={`${detail.latest_analysis_id ?? "none"}:${detail.document_hash ?? "none"}`}
          />
        )}
      </QueryState>
    </StepFrame>
  );
};
