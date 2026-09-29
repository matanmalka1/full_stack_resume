import { ErrorCallout } from "@/ui/ErrorCallout";
import { Callout } from "@/ui/Callout";

interface IntakeFeedbackProps {
  error: Error | null;
  inlineFields: ReadonlySet<string>;
  isStale: boolean;
}

/* Only what the submission reported. A standing note about what creating does used to
   close this list, drawn as a filled success banner before anything had succeeded; its
   sentence was already the job-text field's hint and the commit bar's own line. A field
   the server refused is marked under that field; the callout is the summary. */
export const IntakeFeedback = ({ error, inlineFields, isStale }: IntakeFeedbackProps) => (
  <>
    {isStale ? (
      // role="status" is a Callout prop, not a DOM role; Callout already renders an
      // <output> for it.
      // oxlint-disable-next-line jsx-a11y/prefer-tag-over-role
      <Callout role="status" title="הפרטים השתנו בזמן הבדיקה" tone="neutral">
        התשובה שהתקבלה אינה חלה על מה שמופיע עכשיו. יש ללחוץ שוב על יצירת המועמדות.
      </Callout>
    ) : null}
    {error === null ? null : (
      <ErrorCallout
        error={error}
        fallbackDetail="הפרטים שהוזנו נשארו בטופס. אפשר לנסות שוב."
        inlineFields={inlineFields}
        title="המועמדות לא נוצרה"
      />
    )}
  </>
);
