import { Check, CircleDashed, CircleX, ListChecks, type LucideIcon } from "lucide-react";
import { useMemo, useState } from "react";

import type { RequirementImportance } from "@/api/analyses";
import type { ApplicationDetail } from "@/api/contracts";
import type { DocumentOutline } from "@/api/documents";
import { RequirementFactAction, documentRequirements } from "@/features/preparation";
import { DisclosureSummary } from "@/ui/Disclosure";
import { StatusBadge } from "@/ui/StatusBadge";
import type { Tone } from "@/ui/tone";
import { type RequirementDocumentState, requirementCoverage } from "../model/requirementCoverage";

const stateLabels: Record<RequirementDocumentState, string> = {
  in_document: "מופיעה בטיוטה",
  not_in_document: "לא מופיעה בטיוטה",
  no_facts: "אין עובדה תומכת",
};

const stateTones: Record<RequirementDocumentState, Tone> = {
  in_document: "success",
  not_in_document: "warning",
  no_facts: "neutral",
};

const stateIcons: Record<RequirementDocumentState, LucideIcon> = {
  in_document: Check,
  not_in_document: CircleX,
  no_facts: CircleDashed,
};

const importanceLabels: Record<RequirementImportance, string | null> = {
  mandatory: "חובה",
  preferred: "מועדפת",
  unknown: null,
};

interface DraftRequirementsPanelProps {
  detail: ApplicationDetail;
  /* The draft on screen, unsaved edits included, so a line relinked or removed a moment
     ago already counts. */
  outline: DocumentOutline;
}

/* The job's requirements beside the draft, each marked by whether the draft on screen
   links one of the facts the analysis found supporting it - the same test the backend's
   `REQUIREMENT_NOT_IN_DOCUMENT` applies to the saved document, read live. Nothing here
   matches wording or scores anything.

   Collapsed by default: it is a reference the reader opens, not the work of the screen.
   Silent when the document's own analysis is not the one this client can read. */
export const DraftRequirementsPanel = ({ detail, outline }: DraftRequirementsPanelProps) => {
  const [open, setOpen] = useState(false);
  const requirements = useMemo(() => documentRequirements(detail), [detail]);
  const summary = useMemo(
    () => (requirements === null ? null : requirementCoverage(requirements, outline)),
    [requirements, outline],
  );
  if (summary === null || summary.rows.length === 0) return null;
  const profile = detail.application.profile ?? null;

  return (
    <section
      aria-labelledby="draft-requirements-heading"
      className="border border-cv-border bg-cv-surface p-card-padding max-lg:rounded-surface max-lg:p-3.5"
    >
      <details onToggle={(event) => setOpen(event.currentTarget.open)} open={open}>
        <DisclosureSummary className="text-body font-semibold text-cv-text max-lg:min-h-11" open={open}>
          <span className="inline-flex flex-wrap items-center gap-x-2 gap-y-1">
            <ListChecks aria-hidden="true" className="size-icon-md text-cv-text-muted" />
            <span id="draft-requirements-heading">דרישות המשרה</span>
            <span className="text-support font-normal text-cv-text-muted">
              {summary.inDocument}/{summary.evidenced} מופיעות בטיוטה
              {summary.warned > 0 ? ` · ${summary.warned} דרישות חובה חסרות` : ""}
            </span>
          </span>
        </DisclosureSummary>

        <ul className="mt-3 flex flex-col divide-y divide-cv-border">
          {summary.rows.map(({ requirement, state }) => {
            const importance = importanceLabels[requirement.importance];
            return (
              <li className="flex flex-col gap-2 py-3" key={requirement.requirementId}>
                <div className="flex flex-wrap items-start justify-between gap-x-3 gap-y-2">
                  <p className="min-w-0 flex-1 text-support leading-6 text-cv-text">
                    <bdi>{requirement.text}</bdi>
                    {importance === null ? null : (
                      <span className="ms-2 text-caption font-semibold text-cv-text-muted">{importance}</span>
                    )}
                  </p>
                  <StatusBadge className="shrink-0" icon={stateIcons[state]} tone={stateTones[state]}>
                    {stateLabels[state]}
                  </StatusBadge>
                </div>
                {state === "no_facts" ? <RequirementFactAction profile={profile} requirement={requirement} /> : null}
              </li>
            );
          })}
        </ul>
      </details>
    </section>
  );
};
