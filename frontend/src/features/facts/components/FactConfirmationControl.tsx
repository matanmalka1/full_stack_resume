import { Check } from "lucide-react";
import { useState } from "react";

import type { Fact } from "@/api/contracts";
import { Button } from "@/ui/Button";
import { ConfirmDialog } from "@/ui/ConfirmDialog";
import { ErrorCallout } from "@/ui/ErrorCallout";
import { useConfirmFact } from "../api/mutations";

/* Promoting a pending fact to the source of truth: the one lifecycle step. The design
   draws it as a single command; the person attesting that they read the fact and its
   source - which used to be a checkbox the button waited on - is now the question the
   command asks before it writes, so it stays a deliberate act. Any other status has
   nothing to promote and renders nothing. */
export const FactConfirmationControl = ({ className, fact }: { className?: string; fact: Fact }) => {
  const [asking, setAsking] = useState(false);
  const confirmation = useConfirmFact(fact.fact_id, () => setAsking(false));

  if (fact.status !== "pending") {
    return null;
  }

  return (
    <>
      <Button className={className} onClick={() => setAsking(true)} size="default">
        <Check aria-hidden="true" className="size-icon-md shrink-0" />
        קידום למקור אמת
      </Button>
      <ConfirmDialog
        confirmLabel="קידום למקור אמת"
        headingId="fact-promotion-heading"
        icon={<Check />}
        onCancel={() => {
          confirmation.reset();
          setAsking(false);
        }}
        onConfirm={() => confirmation.mutate()}
        open={asking}
        pending={confirmation.isPending}
        pendingLabel="מקדם…"
        title="לקדם את העובדה למקור אמת?"
      >
        <p className="text-cv-text-muted">
          בדקתי את תוכן העובדה ואת המקור שלה. מרגע הקידום היא יכולה להיכנס לטיוטות, ותיקון שלה ייעשה בעובדה מחליפה.
        </p>
        {confirmation.error === null ? null : (
          <ErrorCallout
            className="mt-3"
            error={confirmation.error}
            fallbackDetail="העובדה לא השתנתה. אפשר לנסות שוב."
            title="מעמד העובדה לא עודכן"
          />
        )}
      </ConfirmDialog>
    </>
  );
};
