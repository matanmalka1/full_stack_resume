import { Plus } from "lucide-react";
import { useId, useState } from "react";

import type { Requirement } from "@/api/analyses";
import { FactCreationDialog, emptyFactForm } from "@/features/facts";
import { Button } from "@/ui/Button";
import { SuccessNotice } from "@/ui/SuccessNotice";

/* A requirement the analysis found no fact for, and the way to record real experience
   for it: the ordinary fact creation dialog, which writes a pending fact. No AI writes
   anything here.

   The requirement is shown as the hint the reader is answering, never seeded as the
   fact's own wording: the posting's sentence is what the employer asked for, not what
   the candidate did. The new fact changes nothing on this screen by itself - it is
   pending until confirmed, and the analysis reads facts when it runs - so the notice
   says what comes next. */
export const RequirementFactAction = ({
  profile,
  requirement,
}: {
  profile: string | null;
  requirement: Requirement;
}) => {
  const id = useId();
  const [open, setOpen] = useState(false);
  const [created, setCreated] = useState(false);

  return (
    <div className="flex flex-col items-start gap-2">
      <Button
        aria-label={`הוסף עובדה לדרישה: ${requirement.text}`}
        onClick={() => {
          setCreated(false);
          setOpen(true);
        }}
        variant="secondary"
      >
        <Plus aria-hidden="true" className="size-icon-md shrink-0" />
        הוסף עובדה
      </Button>
      {created ? (
        <SuccessNotice onDismiss={() => setCreated(false)} title="העובדה נשמרה כממתינה">
          כדי שתיחשב לדרישה יש לאשר אותה במאגר העובדות ולהריץ את הניתוח מחדש.
        </SuccessNotice>
      ) : null}
      {/* Mounted only while open: a closed dialog's intro would put the requirement's text in
          the page a second time, beside the row that already names it. */}
      {open ? (
        <FactCreationDialog
          formId={`${id}-form`}
          headingId={`${id}-heading`}
          initialValues={emptyFactForm(profile)}
          intro={
            <div className="flex flex-col gap-2 text-support leading-6 text-cv-text-muted">
              <p>
                <span className="font-semibold text-cv-text">הדרישה: </span>
                <bdi>{requirement.text}</bdi>
              </p>
              <p>
                יש לתאר ניסיון אמיתי שעונה על הדרישה, במילים שלך. העובדה נוצרת במעמד ממתין, ואישורה הוא פעולה נפרדת.
              </p>
            </div>
          }
          onClose={() => setOpen(false)}
          onCreated={() => setCreated(true)}
          open={open}
          reason={`created for job requirement ${requirement.requirementId}`}
          submitLabel="יצירת עובדה ממתינה"
          title="הוספת עובדה לדרישה"
        />
      ) : null}
    </div>
  );
};
