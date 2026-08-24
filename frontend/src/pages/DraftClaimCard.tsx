import { useEffect, useState } from "react";

import type { DraftClaim, DraftFact, WorkingDraft, WorkingDraftFacts } from "../api/contracts";
import { Button } from "../ui/Button";
import { Callout } from "../ui/Callout";
import { Field } from "../ui/Field";
import { StatusBadge } from "../ui/StatusBadge";
import { TextArea } from "../ui/TextInput";
import { removability } from "./claimRemoval";
import { claimTypeExplanations, claimTypeLabels, claimTypeTones } from "./draftLabels";

interface DraftClaimCardProps {
  claim: DraftClaim;
  draft: WorkingDraft;
  facts: WorkingDraftFacts | undefined;
  onBlur: () => void;
  onEdit: (claim: DraftClaim, text: string) => void;
  onRemove: (claim: DraftClaim) => void;
}

const factRow = (fact: DraftFact) => (
  <li className="text-support leading-6 text-cv-text-muted" key={fact.fact_id}>
    <span dir="auto">{fact.text ?? "לא ניתן לקרוא את העובדה הזו מהידע."}</span>
  </li>
);

/* A.4 frame 3: the claim, its status in words, the facts behind it, and what may be done
   to it. The status is the backend's `claim_type`, not a judgement made here, and the
   supporting facts are named by their text - a user never has to read a fact ID. */
export const DraftClaimCard = ({
  claim,
  draft,
  facts,
  onBlur,
  onEdit,
  onRemove,
}: DraftClaimCardProps) => {
  const linked = (facts?.facts ?? []).filter((fact) => claim.fact_ids.includes(fact.fact_id));
  const removal = removability(claim, draft, facts);
  const [text, setText] = useState(claim.text);

  /* The server's text wins whenever it changes underneath: a regeneration, a rebuilt
     selection, or the version the user kept after a conflict. Local typing is not lost by
     this - an unsaved edit is held in the autosave buffer, not here. */
  useEffect(() => {
    setText(claim.text);
  }, [claim.text]);

  return (
    <li className="rounded-surface border border-cv-border bg-cv-surface p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <StatusBadge tone={claimTypeTones[claim.claim_type]}>
          {claimTypeLabels[claim.claim_type]}
        </StatusBadge>
        {removal.route === "none" ? null : (
          <Button onClick={() => onRemove(claim)} variant="secondary">
            הסרת השורה
          </Button>
        )}
      </div>

      <Field className="mt-3" label="טקסט השורה">
        {(control) => (
          <TextArea
            {...control}
            className="min-h-20"
            dir="auto"
            onBlur={onBlur}
            onChange={(event) => {
              setText(event.target.value);
              onEdit(claim, event.target.value);
            }}
            value={text}
          />
        )}
      </Field>

      <p className="mt-2 text-support leading-6 text-cv-text-muted">
        {claimTypeExplanations[claim.claim_type]}
      </p>

      {claim.claim_type === "pending" && claim.pending_reason !== null ? (
        <Callout className="mt-3" title="הטקסט הזה חוסם אישור" tone="blocker">
          <p dir="auto">{claim.pending_reason}</p>
        </Callout>
      ) : null}

      {linked.length === 0 ? null : (
        <div className="mt-3">
          <p className="text-support font-medium text-cv-text">העובדות שמאחורי השורה</p>
          <ul className="mt-1 flex list-disc flex-col gap-1 ps-5">{linked.map(factRow)}</ul>
        </div>
      )}

      {removal.route === "none" && removal.reason !== undefined ? (
        <p className="mt-3 text-support leading-6 text-cv-text-muted">{removal.reason}</p>
      ) : null}

      {removal.route === "selection" ? (
        <p className="mt-3 text-support leading-6 text-cv-text-muted">
          הסרת השורה מחריגה את העובדה שמאחוריה ובונה את הטיוטה מחדש בלעדיה.
        </p>
      ) : null}
    </li>
  );
};
