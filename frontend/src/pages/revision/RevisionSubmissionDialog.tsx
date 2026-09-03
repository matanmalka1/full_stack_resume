import { Button } from "../../ui/Button";
import { Dialog } from "../../ui/Dialog";
import { Field } from "../../ui/Field";
import { TextInput } from "../../ui/TextInput";

interface RevisionSubmissionDialogProps {
  onClose: () => void;
  onSubmit: () => void;
  onSubmittedAtChange: (value: string) => void;
  open: boolean;
  pending: boolean;
  submittedAt: string;
  submittedAtValid: boolean;
}

export const RevisionSubmissionDialog = ({
  onClose,
  onSubmit,
  onSubmittedAtChange,
  open,
  pending,
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
          disabled={!submittedAtValid}
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
    title="רישום הגשה קבועה"
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
