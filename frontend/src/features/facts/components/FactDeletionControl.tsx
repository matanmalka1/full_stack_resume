import { useState } from "react";
import { Trash2 } from "lucide-react";

import type { Fact } from "@/api/contracts";
import { Button } from "@/ui/Button";
import { Callout } from "@/ui/Callout";
import { ErrorCallout } from "@/ui/ErrorCallout";
import { useDeleteFact } from "../api/mutations";

/* Deletion is one-way: nothing brings the fact back to `list_facts` or a Profile pool.
   Unlike `FactConfirmationControl`'s forward step, this needs its own confirmation stage -
   the attestation checkbox alone reads the same as "I confirm the fact", and
   deleting is not a step in the same direction. The button opens a confirmation panel
   that states plainly what stays (history, Submissions), what does not (default listings,
   attachment targets, new selections), and that a document using the fact loses its
   approval (state-and-use-cases §6), and only that panel's own
   button sends the request. An already-deleted fact renders nothing: there is no
   undelete in this phase. */
export const FactDeletionControl = ({ fact }: { fact: Fact }) => {
  const [confirming, setConfirming] = useState(false);
  const deletion = useDeleteFact(fact.fact_id, () => setConfirming(false));

  if (fact.status === "deleted") {
    return null;
  }

  if (!confirming) {
    return (
      <Button onClick={() => setConfirming(true)} size="compact" variant="ghost">
        <Trash2 aria-hidden="true" className="size-icon-md shrink-0" />
        מחיקת העובדה
      </Button>
    );
  }

  return (
    <div className="flex flex-col gap-3 rounded-control border border-cv-blocker bg-cv-surface p-4">
      <Callout title="הפעולה סופית ואינה הפיכה" tone="warning">
        העובדה תוסר מרשימת העובדות המוצגת כברירת מחדל ולא תוצע כיעד צירוף חדש. ההיסטוריה שלה וכל הגשה שכבר נרשמה יישארו
        ללא שינוי ונגישים לצפייה. מסמך קורות חיים שמשתמש בה לא ישתנה, אבל האישור שלו יפוג, ויהיה צורך לפתור את השימוש
        בעובדה לפני אישור מחדש.
      </Callout>
      <div className="flex flex-wrap justify-end gap-2">
        <Button onClick={() => setConfirming(false)} size="compact" variant="secondary">
          ביטול
        </Button>
        <Button onClick={() => deletion.mutate()} pending={deletion.isPending} size="compact" variant="destructive">
          אישור מחיקת העובדה
        </Button>
      </div>
      {deletion.error === null ? null : (
        <ErrorCallout
          error={deletion.error}
          fallbackDetail="העובדה לא השתנתה. אפשר לנסות שוב."
          title="העובדה לא נמחקה"
        />
      )}
    </div>
  );
};
