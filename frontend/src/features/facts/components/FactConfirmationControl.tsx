import { useState } from "react";

import type { Fact } from "@/api/contracts";
import { ErrorCallout } from "@/ui/ErrorCallout";
import { Button } from "@/ui/Button";
import { Checkbox } from "@/ui/Checkbox";
import { useConfirmFact } from "../api/mutations";

/* Confirming a pending fact makes it canonical: the one lifecycle step. It is a
   deliberate act: the checkbox is the person attesting they read the fact and its source,
   so it is required rather than advisory. Any other status has nothing to confirm and
   renders nothing. */
export const FactConfirmationControl = ({ fact }: { fact: Fact }) => {
  const [attested, setAttested] = useState(false);
  const confirmation = useConfirmFact(fact.fact_id, () => setAttested(false));

  if (fact.status !== "pending") {
    return null;
  }

  return (
    <div className="flex flex-col gap-3 rounded-control border border-cv-border bg-cv-surface p-4">
      <Checkbox checked={attested} onChange={(event) => setAttested(event.currentTarget.checked)}>
        בדקתי את תוכן העובדה והמקור ואני מאשר את שינוי המעמד
      </Checkbox>
      {/* On a phone the step is the screen's one command, pinned above the bottom bar where
          a thumb finds it; the attestation it waits on stays here in the body. */}
      <div className="max-lg:fixed max-lg:inset-x-0 max-lg:bottom-(--cv-bottom-nav-height) max-lg:z-(--cv-z-sticky) max-lg:border-t max-lg:border-cv-border max-lg:bg-cv-surface max-lg:p-4">
        <Button
          className="w-full max-lg:min-h-12 max-lg:rounded-surface max-lg:text-body"
          disabled={!attested}
          onClick={() => confirmation.mutate()}
          pending={confirmation.isPending}
        >
          אישור העובדה כמקור אמת
        </Button>
      </div>
      {confirmation.error === null ? null : (
        <ErrorCallout
          error={confirmation.error}
          fallbackDetail="העובדה לא השתנתה. אפשר לנסות שוב."
          title="מעמד העובדה לא עודכן"
        />
      )}
    </div>
  );
};
