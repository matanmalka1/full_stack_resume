import type { ClassificationDecisions } from "@/api/analyses";
import { Field } from "@/ui/Field";
import { Switch } from "@/ui/Switch";
import { Textarea } from "@/ui/Input";

/* An acknowledgement of a stated risk, drawn as one. A row of plain checkboxes made
   "I understand the requirements were never read" look like an option among options; the
   amber card and the switch say that turning it on is the decision itself. */
const RiskAcknowledgement = ({
  checked,
  children,
  description,
  disabled,
  onChange,
}: {
  checked: boolean;
  children: string;
  description: string;
  disabled: boolean;
  onChange: (checked: boolean) => void;
}) => (
  <div className="rounded-control border border-cv-warning/40 border-s-2 border-s-cv-warning bg-cv-warning-soft p-4">
    <Switch checked={checked} description={description} disabled={disabled} onChange={onChange}>
      {children}
    </Switch>
  </div>
);

/* What the submission will carry from the gap list above, and the reason recorded with
   it. One reason per submission rather than one per gap, because that is what the server
   stores: every gap accepted in the same commit is recorded with the same sentence.

   Nothing here can mark a gap. When none is marked the fields still appear, saying where
   the mark is taken - the alternative was a panel that names the blocker and shows no way
   to answer it. */
const GapAcceptanceFields = ({
  acceptance,
  decisions,
  disabled,
  onChange,
}: {
  acceptance: { acceptable: number; marked: number };
  decisions: ClassificationDecisions;
  disabled: boolean;
  onChange: (decisions: ClassificationDecisions) => void;
}) => (
  <div className="flex flex-col gap-3">
    <p className="text-support leading-6 text-cv-text-muted" dir="auto">
      {acceptance.marked === 0
        ? "סימון פער חוסם ברשימת הפערים שלמעלה הוא ההכרעה שפותחת את המשך התהליך. הסימון אינו הופך את הפער למכוסה ואינו מתיר טענה שאין לה עובדה — הוא רושם שהמשכת ביודעין."
        : `${acceptance.marked} מתוך ${acceptance.acceptable} פערים חוסמים מסומנים לקבלה. הסימון אינו הופך את הפער למכוסה ואינו מתיר טענה שאין לה עובדה — הוא רושם שהמשכת ביודעין.`}
    </p>

    <Field hint="הסיבה נרשמת יחד עם כל הפערים שסומנו בשליחה הזו." label="סיבת הקבלה" optional>
      {(control) => (
        <Textarea
          {...control}
          className="min-h-20"
          dir="auto"
          disabled={disabled}
          /* The server's own limit, stated to the control rather than re-checked after
             the fact: a longer reason is refused there, and the field is what keeps the
             reader from writing one. */
          maxLength={500}
          onChange={(event) => onChange({ ...decisions, acceptance_reason: event.target.value })}
          value={decisions.acceptance_reason ?? ""}
        />
      )}
    </Field>
  </div>
);

interface ReviewDecisionFormProps {
  decisions: ClassificationDecisions;
  disabled: boolean;
  /* How many hard gaps are marked, and whether there is any gap that can be marked at
     all. The marks themselves are taken on the gaps above this panel, so what this form
     owns is the reason recorded with them and the account of what is about to be sent. */
  gapAcceptance: { acceptable: number; marked: number } | null;
  onChange: (decisions: ClassificationDecisions) => void;
  showFit: boolean;
  showIncompleteAnalysis: boolean;
}

export const ReviewDecisionForm = ({
  decisions,
  disabled,
  gapAcceptance,
  onChange,
  showFit,
  showIncompleteAnalysis,
}: ReviewDecisionFormProps) => {
  return (
    <div className="flex flex-col gap-5">
      {showIncompleteAnalysis ? (
        <RiskAcknowledgement
          checked={decisions.accept_incomplete_analysis}
          description="הניתוח לא הצליח לקרוא את דרישות המשרה. בחירת מסלול או פרופיל אינה פותרת זאת, ואישור זה נרשם על הניתוח הזה בלבד - ניתוח חדש יחסום שוב."
          disabled={disabled}
          onChange={(accept_incomplete_analysis) => onChange({ ...decisions, accept_incomplete_analysis })}
        >
          אני מבין שהדרישות לא נקראו ומבקש להמשיך
        </RiskAcknowledgement>
      ) : null}

      {showFit ? (
        <RiskAcknowledgement
          checked={decisions.accept_low_fit}
          description="אישור זה נרשם על הניתוח עצמו ופותר את ההתאמה הנמוכה בלבד. פער חוסם נדרש להכרעה נפרדת, על הפער עצמו."
          disabled={disabled}
          onChange={(accept_low_fit) => onChange({ ...decisions, accept_low_fit })}
        >
          אני מאשר את ההתאמה הנמוכה ומבקש להמשיך
        </RiskAcknowledgement>
      ) : null}

      {gapAcceptance === null ? null : (
        <GapAcceptanceFields acceptance={gapAcceptance} decisions={decisions} disabled={disabled} onChange={onChange} />
      )}
    </div>
  );
};
