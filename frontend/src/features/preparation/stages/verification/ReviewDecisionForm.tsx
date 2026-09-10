import type { Classification, ClassificationDecisions } from "@/api/analyses";
import { Disclosure } from "@/ui/Disclosure";
import { Field } from "@/ui/Field";
import { Select } from "@/ui/Select";
import { Switch } from "@/ui/Switch";
import { Textarea } from "@/ui/Input";
import { emphasisLabels, languageLabels, optionsFrom, profileLabels, trackLabels } from "../../model/analysisLabels";

const NO_OVERRIDE = "";

/* The four overrides differ only in their label, their option map, and which field they
   set, so they are one component rather than four near-identical blocks. `null` is the
   absent decision and `""` its representation in the DOM; they are converted here so no
   call site has to remember that a blank select means "withhold", not "clear". */
interface OverrideFieldProps<T extends string> {
  /* What the analysis decided, named. The withhold option used to read "השארת הבחירה
     הנוכחית" beside the values it was sitting among, so the one option that is not a
     value looked like one - and which value it would leave in place was nowhere on
     screen. */
  current: string | null;
  /* Whether leaving this field on its current value is itself the decision, not the
     absence of one. A field under classification review confirms the analysis's guess
     when kept, so its default option reads as a confirmation rather than a withholding -
     the two say opposite things about whether a press is still owed. */
  confirmsCurrent?: boolean;
  disabled: boolean;
  hint?: string;
  label: string;
  labels: Record<T, string>;
  onSelect: (value: T | null) => void;
  optional?: boolean;
  value: T | null;
}

const OverrideField = <T extends string>({
  current,
  confirmsCurrent,
  disabled,
  hint,
  label,
  labels,
  onSelect,
  optional,
  value,
}: OverrideFieldProps<T>) => (
  <Field hint={hint ?? (current === null ? undefined : `כרגע: ${current}`)} label={label} optional={optional}>
    {(control) => (
      <Select
        {...control}
        disabled={disabled}
        onChange={(event) => onSelect(event.target.value === NO_OVERRIDE ? null : (event.target.value as T))}
        value={value ?? NO_OVERRIDE}
      >
        <option value={NO_OVERRIDE}>
          {current === null
            ? "השארת הבחירה הנוכחית"
            : `${confirmsCurrent ? "אישור הבחירה הנוכחית" : "השארת הבחירה הנוכחית"} — ${current}`}
        </option>
        {optionsFrom(labels).map(([option, optionLabel]) => (
          <option key={option} value={option}>
            {optionLabel}
          </option>
        ))}
      </Select>
    )}
  </Field>
);

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
      {acceptance.acceptable === 0
        ? "אין פער חוסם שאפשר להכריע עליו מכאן. פער שנרשם בניתוח ישן דורש ניתוח מחדש של המשרה."
        : acceptance.marked === 0
          ? "סימון פער חוסם ברשימת הפערים שלמעלה הוא ההכרעה שפותחת את המשך התהליך. הסימון אינו הופך את הפער למכוסה ואינו מתיר טענה שאין לה עובדה — הוא רושם שהמשכת ביודעין."
          : `${acceptance.marked} מתוך ${acceptance.acceptable} פערים חוסמים מסומנים לקבלה. הסימון אינו הופך את הפער למכוסה ואינו מתיר טענה שאין לה עובדה — הוא רושם שהמשכת ביודעין.`}
    </p>

    {acceptance.acceptable === 0 ? null : (
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
    )}
  </div>
);

interface ReviewDecisionFormProps {
  /* The analysis under decision, read only to name what each control would replace. */
  classification: Classification | null;
  decisions: ClassificationDecisions;
  disabled: boolean;
  /* How many hard gaps are marked, and whether there is any gap that can be marked at
     all. The marks themselves are taken on the gaps above this panel, so what this form
     owns is the reason recorded with them and the account of what is about to be sent. */
  gapAcceptance: { acceptable: number; marked: number } | null;
  onChange: (decisions: ClassificationDecisions) => void;
  showClassification: boolean;
  showFit: boolean;
  showIncompleteAnalysis: boolean;
}

export const ReviewDecisionForm = ({
  classification,
  decisions,
  disabled,
  gapAcceptance,
  onChange,
  showClassification,
  showFit,
  showIncompleteAnalysis,
}: ReviewDecisionFormProps) => {
  /* The four terms as the analysis recorded them, read through the same label maps the
     analysis summary uses, so "leave as it is" names the value the reader saw rather than
     a second wording of it. A term the analysis never recorded has nothing to name and
     leaves the option as the bare sentence it always was. */
  const current = {
    emphasis: classification?.emphasis == null ? null : emphasisLabels[classification.emphasis],
    language: classification?.language == null ? null : languageLabels[classification.language],
    profile: classification?.profile == null ? null : profileLabels[classification.profile],
    track: classification?.track == null ? null : trackLabels[classification.track],
  };

  return (
    <div className="flex flex-col gap-5">
      {showClassification ? (
        <div className="flex flex-col gap-4">
          <div>
            <h3 className="text-support font-semibold text-cv-text">בחירת סוג קורות החיים</h3>
            <p className="mt-1 text-support leading-6 text-cv-text-muted">
              אשרו את הסיווג שהניתוח הציע, או שנו את המסלול או הפרופיל. שדה שיישאר על הבחירה הנוכחית יאושר כפי שנקבע
              בניתוח — אין צורך לשנות ערך נכון רק כדי להמשיך.
            </p>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <OverrideField
              confirmsCurrent
              current={current.track}
              disabled={disabled}
              label="מסלול"
              labels={trackLabels}
              onSelect={(track_override) => onChange({ ...decisions, track_override })}
              value={decisions.track_override ?? null}
            />
            <OverrideField
              confirmsCurrent
              current={current.profile}
              disabled={disabled}
              label="פרופיל"
              labels={profileLabels}
              onSelect={(profile_override) => onChange({ ...decisions, profile_override })}
              value={decisions.profile_override ?? null}
            />
          </div>

          <Disclosure summary="אפשרויות נוספות: דגש ושפת קורות החיים">
            <div className="grid gap-4 md:grid-cols-2">
              <OverrideField
                current={current.emphasis}
                disabled={disabled}
                label="דגש"
                labels={emphasisLabels}
                onSelect={(emphasis_override) => onChange({ ...decisions, emphasis_override })}
                optional
                value={decisions.emphasis_override ?? null}
              />
              <OverrideField
                current={current.language}
                disabled={disabled}
                label="שפת קורות החיים"
                labels={languageLabels}
                onSelect={(language_override) => onChange({ ...decisions, language_override })}
                optional
                value={decisions.language_override ?? null}
              />
            </div>
          </Disclosure>
        </div>
      ) : null}

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
