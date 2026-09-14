import { FileCheck2 } from "lucide-react";

import { ErrorCallout } from "@/ui/ErrorCallout";
import { Callout } from "@/ui/Callout";

interface IntakeFeedbackProps {
  error: Error | null;
  isStale: boolean;
  serverValidationFailed: boolean;
}

export const IntakeFeedback = ({ error, isStale, serverValidationFailed }: IntakeFeedbackProps) => (
  <>
    {isStale ? (
      // role="status" is a Callout prop, not a DOM role; Callout already renders an
      // <output> for it.
      // oxlint-disable-next-line jsx-a11y/prefer-tag-over-role
      <Callout role="status" title="הקלט השתנה מאז הבדיקה" tone="neutral">
        הקלט השתנה בזמן הפנייה לשרת, ולכן התשובה אינה חלה על מה שמופיע עכשיו. יש ללחוץ שוב על יצירת מועמדות כדי לבדוק את
        הקלט הנוכחי.
      </Callout>
    ) : null}
    {serverValidationFailed ? (
      <Callout role="alert" title="יש לתקן את השדות המסומנים" tone="blocker">
        השרת דחה את הערכים בשדות האלה. התוכן שהוזן נשאר במקומו, ואפשר לתקן ולשלוח שוב.
      </Callout>
    ) : null}
    {error === null ? null : (
      <ErrorCallout
        error={error}
        fallbackDetail="הפנייה לשרת נכשלה. מה שהוזן נשמר בטופס וניתן לנסות שוב."
        fallbackTitle="יצירת המועמדות נכשלה"
      />
    )}
    <div className="flex items-start gap-2 rounded-control border border-cv-success/25 bg-cv-success-soft p-3 text-support text-cv-text">
      <FileCheck2 aria-hidden="true" className="mt-0.5 size-icon-md shrink-0 text-cv-success" />
      <p>יצירת המועמדות שומרת את הטקסט בדיוק כפי שהוזן בתצלום משרה קבוע, ואז מתחילה את ניתוח ההתאמה.</p>
    </div>
  </>
);
