import { useState } from "react";
import { MoreVertical, Trash2 } from "lucide-react";

import type { Fact } from "@/api/contracts";
import { ConfirmDialog } from "@/ui/ConfirmDialog";
import { Dialog } from "@/ui/Dialog";
import { ErrorCallout } from "@/ui/ErrorCallout";
import { IconButton } from "@/ui/IconButton";
import { ListCard, ListRow } from "@/ui/ListCard";
import { useDeleteFact } from "../api/mutations";

/* The fact's ⋮ menu, which holds its one rare command: deletion. Deletion is one-way -
   nothing brings the fact back to the pool or a Profile - so choosing it from the menu
   asks once more, stating plainly what stays (history, Submissions), what does not
   (default listings, attachment targets, new selections), and that a document using the
   fact loses its approval (state-and-use-cases §6). Only that question's own command
   sends the request. An already-deleted fact has no menu: there is no undelete. */
export const FactDeletionControl = ({ fact, onDeleted }: { fact: Fact; onDeleted: () => void }) => {
  const [step, setStep] = useState<"closed" | "menu" | "confirm">("closed");
  const deletion = useDeleteFact(fact.fact_id, () => {
    setStep("closed");
    onDeleted();
  });

  if (fact.status === "deleted") {
    return null;
  }

  return (
    <>
      <IconButton aria-label="אפשרויות נוספות" onClick={() => setStep("menu")} variant="quiet">
        <MoreVertical aria-hidden="true" className="size-icon-md" />
      </IconButton>
      <Dialog
        headingId="fact-actions-heading"
        onClose={() => setStep((current) => (current === "menu" ? "closed" : current))}
        open={step === "menu"}
        title="פעולות על העובדה"
      >
        <ListCard>
          <ListRow
            icon={Trash2}
            label="מחיקת העובדה"
            onClick={() => {
              deletion.reset();
              setStep("confirm");
            }}
          />
        </ListCard>
      </Dialog>
      <ConfirmDialog
        confirmLabel="מחיקת העובדה"
        confirmVariant="destructive"
        headingId="fact-deletion-heading"
        icon={<Trash2 />}
        onCancel={() => setStep("closed")}
        onConfirm={() => deletion.mutate()}
        open={step === "confirm"}
        pending={deletion.isPending}
        pendingLabel="מוחק…"
        title="למחוק את העובדה?"
      >
        <p className="text-cv-text-muted">
          הפעולה סופית ואינה הפיכה. העובדה תוסר מהמאגר ולא תוצע כיעד צירוף חדש. ההיסטוריה שלה וכל הגשה שכבר נרשמה יישארו
          ללא שינוי. מסמך קורות חיים שמשתמש בה לא ישתנה, אבל האישור שלו יפוג עד שהשימוש בעובדה ייפתר.
        </p>
        {deletion.error === null ? null : (
          <ErrorCallout
            className="mt-3"
            error={deletion.error}
            fallbackDetail="העובדה לא השתנתה. אפשר לנסות שוב."
            title="העובדה לא נמחקה"
          />
        )}
      </ConfirmDialog>
    </>
  );
};
