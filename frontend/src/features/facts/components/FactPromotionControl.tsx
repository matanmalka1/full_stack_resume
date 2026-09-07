import { useState } from "react";

import type { Fact } from "@/api/contracts";
import { ErrorCallout } from "@/ui/ErrorCallout";
import { Button } from "@/ui/Button";
import { Checkbox } from "@/ui/Checkbox";
import { useTransitionFact } from "../api/mutations";

/* Moving a fact forward along `pending -> confirmed -> canonical`. Each step is one
   deliberate act: the checkbox is the person attesting they read the fact and its
   source, so it is required rather than advisory, and it clears again after the write so
   the next step is attested on its own. A canonical fact has nowhere further to go and
   renders nothing. */
export const FactPromotionControl = ({ fact }: { fact: Fact }) => {
  const [attested, setAttested] = useState(false);
  const transition = useTransitionFact(fact.fact_id, () => setAttested(false));

  if (fact.status !== "pending" && fact.status !== "confirmed") {
    return null;
  }

  const promoting = fact.status === "confirmed";

  return (
    <div className="flex flex-col gap-3 rounded-control border border-cv-border bg-cv-surface p-4">
      {transition.error === null ? null : (
        <ErrorCallout
          error={transition.error}
          fallbackDetail="מקור הידע לא השתנה ואפשר לנסות שוב."
          fallbackTitle="לא ניתן לעדכן את העובדה"
        />
      )}
      <Checkbox checked={attested} onChange={(event) => setAttested(event.currentTarget.checked)}>
        בדקתי את תוכן העובדה והמקור ואני מאשר את שינוי המעמד
      </Checkbox>
      <Button
        disabled={!attested}
        onClick={() => transition.mutate(promoting ? "promote" : "confirm")}
        pending={transition.isPending}
      >
        {promoting ? "קידום למקור אמת" : "אישור העובדה"}
      </Button>
    </div>
  );
};
