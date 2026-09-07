import { useMutation } from "@tanstack/react-query";
import { RotateCcw } from "lucide-react";

import { reconcile } from "@/api/maintenance";
import { ErrorCallout } from "@/app/ErrorCallout";
import { Button } from "@/ui/Button";
import { Card } from "@/ui/Card";
import { SectionHeader } from "@/ui/SectionHeader";
import { ReconciliationReport } from "./ReconciliationReport";

export const ReconciliationPanel = () => {
  const reconciliation = useMutation({ mutationFn: reconcile });

  return (
    <Card aria-labelledby="reconciliation-heading" className="bg-cv-surface p-5 shadow-surface sm:p-6">
      <SectionHeader
        constrainDescription
        description="התאמה בין מסד הנתונים, התוצרים השמורים ומחזור חיי העובדות. הבדיקה מדווחת בלבד ואינה מתקנת נתונים."
        headingId="reconciliation-heading"
        icon={RotateCcw}
        title="בדיקת תקינות"
      />
      <div className="mt-4 flex flex-col items-start gap-6">
        <Button
          onClick={() => reconciliation.mutate()}
          pending={reconciliation.isPending}
          pendingLabel="בודק התאמה…"
          type="button"
        >
          הפעלת בדיקת התאמה
        </Button>
        {reconciliation.data === undefined ? null : <ReconciliationReport report={reconciliation.data} />}
        {reconciliation.error === null ? null : (
          <ErrorCallout
            error={reconciliation.error}
            fallbackDetail="לא ניתן היה להשלים את בדיקת ההתאמה."
            fallbackTitle="בדיקת ההתאמה נכשלה"
          />
        )}
      </div>
    </Card>
  );
};
