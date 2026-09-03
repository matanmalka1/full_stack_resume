import { Button } from "../../ui/Button";
import { Callout } from "../../ui/Callout";
import { Checkbox } from "../../ui/Checkbox";
import { Dialog } from "../../ui/Dialog";
import { Field } from "../../ui/Field";
import { TextInput } from "../../ui/TextInput";
import { formatDateTime } from "../../ui/formatDateTime";

interface RevisionSubmissionDialogProps {
  onClose: () => void;
  onRepeatAcknowledgedChange: (value: boolean) => void;
  onSubmit: () => void;
  onSubmittedAtChange: (value: string) => void;
  open: boolean;
  pending: boolean;
  /* When this revision is already on record as submitted. Its presence turns the dialog
     from the plain recording into the exception it now is, and the acknowledgement below
     is what the reader has to state before a second one can be written. */
  previousSubmittedAt: string | null;
  repeatAcknowledged: boolean;
  submittedAt: string;
  submittedAtValid: boolean;
}

export const RevisionSubmissionDialog = ({
  onClose,
  onRepeatAcknowledgedChange,
  onSubmit,
  onSubmittedAtChange,
  open,
  pending,
  previousSubmittedAt,
  repeatAcknowledged,
  submittedAt,
  submittedAtValid,
}: RevisionSubmissionDialogProps) => (
  <Dialog
    dismissible={false}
    footer={
      <>
        <Button onClick={onClose} variant="secondary">
          חזרה
        </Button>
        <Button
          disabled={!submittedAtValid || (previousSubmittedAt !== null && !repeatAcknowledged)}
          form="revision-submission-form"
          pending={pending}
          pendingLabel="רושם…"
          type="submit"
        >
          אישור ורישום ההגשה
        </Button>
      </>
    }
    headingId="submission-dialog-heading"
    onClose={onClose}
    open={open}
    title={previousSubmittedAt === null ? "רישום הגשה קבועה" : "רישום הגשה נוספת של אותה גרסה"}
  >
    <form
      id="revision-submission-form"
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit();
      }}
    >
      <p className="mb-4">
        הרישום קבוע ומתייחס לגרסה ולקובץ ה־PDF המוצגים במסך הזה. הוא לא יפתור גרסה אחרת או קובץ אחר בזמן השמירה.
      </p>
      {previousSubmittedAt === null ? null : (
        <div className="mb-4 flex flex-col gap-3">
          <Callout title="הגרסה הזו כבר נרשמה כמוגשת" tone="warning">
            {`ההגשה הקיימת נרשמה ${formatDateTime(previousSubmittedAt)}. הרישום הקיים לא ישתנה — יתווסף לו אירוע הגשה נוסף.`}
          </Callout>
          <Checkbox
            checked={repeatAcknowledged}
            hint="למשל הגשה חוזרת דרך ערוץ אחר. אם ההגשה כבר נרשמה, אין צורך לרשום אותה שוב."
            onChange={(event) => onRepeatAcknowledgedChange(event.target.checked)}
          >
            אני מבקש לרשום הגשה נוספת של אותה גרסה
          </Checkbox>
        </div>
      )}
      <Field label="מועד ההגשה">
        {(control) => (
          <TextInput
            {...control}
            onChange={(event) => onSubmittedAtChange(event.target.value)}
            required
            type="datetime-local"
            value={submittedAt}
          />
        )}
      </Field>
    </form>
  </Dialog>
);
