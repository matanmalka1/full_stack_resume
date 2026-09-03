import type { ClassificationDecisions } from "../../api/analyses";
import { Checkbox } from "../../ui/Checkbox";
import { Field } from "../../ui/Field";
import { Select } from "../../ui/Select";
import { TextArea } from "../../ui/TextInput";
import { emphasisLabels, languageLabels, optionsFrom, profileLabels, trackLabels } from "./analysisLabels";

/* Which control answers which review reason. A `Record` over exactly the codes this
   screen owns, so a review reason added to the backend falls through to being named as
   belonging elsewhere instead of quietly acquiring an unrelated control.

   This is presentation over codes the projection literally sends. Which reasons exist,
   and whether the action is available at all, stay the projection's answer. */
export const CLASSIFICATION_REASON = "MATERIAL_CLASSIFICATION_AMBIGUITY";

export const FIT_REASON = "LOW_FIT_REQUIRES_ACCEPTANCE";

/* Its own reason with its own control, and deliberately not the fit checkbox's. The two
   were one entry here, which made the fit acceptance claim to answer a hard gap: that
   acceptance is recorded on the analysis, while a gap acceptance is recorded per
   requirement on the SelectionPlan, and the server clears this reason only for the
   latter. Marking the fit therefore re-derived the analysis and left the blocker exactly
   where it was. */
export const GAP_REASON = "HARD_GAP_REQUIRES_DECISION";

export const INCOMPLETE_ANALYSIS_REASON = "ANALYSIS_INCOMPLETE";

export const REVIEW_REASONS_THIS_SCREEN_OWNS: Record<string, true> = {
  [CLASSIFICATION_REASON]: true,
  [INCOMPLETE_ANALYSIS_REASON]: true,
  [FIT_REASON]: true,
  [GAP_REASON]: true,
};

export const emptyDecisions: ClassificationDecisions = {
  track_override: null,
  profile_override: null,
  emphasis_override: null,
  language_override: null,
  accept_low_fit: false,
  accept_incomplete_analysis: false,
  accepted_requirement_ids: [],
  acceptance_reason: null,
};

/* The form's own rule, and the only one it keeps: an empty submission is not a
   submission. It is not a copy of the server's "the submitted decisions change nothing"
   refusal, which also fires when a set value equals one already recorded - that answer
   stays the server's and is presented as it arrives. */
export const hasDecision = (decisions: ClassificationDecisions): boolean =>
  decisions.accept_low_fit ||
  decisions.accept_incomplete_analysis ||
  decisions.track_override != null ||
  decisions.profile_override != null ||
  decisions.emphasis_override != null ||
  decisions.language_override != null ||
  decisions.accepted_requirement_ids.length > 0;

const NO_OVERRIDE = "";

/* The four overrides differ only in their label, their option map, and which field they
   set, so they are one component rather than four near-identical blocks. `null` is the
   absent decision and `""` its representation in the DOM; they are converted here so no
   call site has to remember that a blank select means "withhold", not "clear". */
interface OverrideFieldProps<T extends string> {
  disabled: boolean;
  hint?: string;
  label: string;
  labels: Record<T, string>;
  onSelect: (value: T | null) => void;
  value: T | null;
}

const OverrideField = <T extends string>({ disabled, hint, label, labels, onSelect, value }: OverrideFieldProps<T>) => (
  <Field hint={hint} label={label}>
    {(control) => (
      <Select
        {...control}
        disabled={disabled}
        onChange={(event) => onSelect(event.target.value === NO_OVERRIDE ? null : (event.target.value as T))}
        value={value ?? NO_OVERRIDE}
      >
        <option value={NO_OVERRIDE}>ללא שינוי</option>
        {optionsFrom(labels).map(([option, optionLabel]) => (
          <option key={option} value={option}>
            {optionLabel}
          </option>
        ))}
      </Select>
    )}
  </Field>
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
          <TextArea
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
  decisions,
  disabled,
  gapAcceptance,
  onChange,
  showClassification,
  showFit,
  showIncompleteAnalysis,
}: ReviewDecisionFormProps) => (
  <div className="flex flex-col gap-6">
    {showClassification ? (
      <>
        <OverrideField
          disabled={disabled}
          hint="בחירה במסלול או בפרופיל היא ההחלטה שפותרת אי־בהירות בסיווג."
          label="מסלול"
          labels={trackLabels}
          onSelect={(track_override) => onChange({ ...decisions, track_override })}
          value={decisions.track_override ?? null}
        />
        <OverrideField
          disabled={disabled}
          label="פרופיל"
          labels={profileLabels}
          onSelect={(profile_override) => onChange({ ...decisions, profile_override })}
          value={decisions.profile_override ?? null}
        />
        <OverrideField
          disabled={disabled}
          label="דגש"
          labels={emphasisLabels}
          onSelect={(emphasis_override) => onChange({ ...decisions, emphasis_override })}
          value={decisions.emphasis_override ?? null}
        />
        <OverrideField
          disabled={disabled}
          label="שפת קורות החיים"
          labels={languageLabels}
          onSelect={(language_override) => onChange({ ...decisions, language_override })}
          value={decisions.language_override ?? null}
        />
      </>
    ) : null}

    {showIncompleteAnalysis ? (
      <Checkbox
        checked={decisions.accept_incomplete_analysis}
        disabled={disabled}
        hint="הניתוח לא הצליח לקרוא את דרישות המשרה. בחירת מסלול או פרופיל אינה פותרת זאת, ואישור זה נרשם על הניתוח הזה בלבד - ניתוח חדש יחסום שוב."
        onChange={(event) => onChange({ ...decisions, accept_incomplete_analysis: event.target.checked })}
      >
        אני מבין שהדרישות לא נקראו ומבקש להמשיך
      </Checkbox>
    ) : null}

    {showFit ? (
      <Checkbox
        checked={decisions.accept_low_fit}
        disabled={disabled}
        hint="אישור זה נרשם על הניתוח עצמו ופותר את ההתאמה הנמוכה בלבד. פער חוסם נדרש להכרעה נפרדת, על הפער עצמו."
        onChange={(event) => onChange({ ...decisions, accept_low_fit: event.target.checked })}
      >
        אני מאשר את ההתאמה הנמוכה ומבקש להמשיך
      </Checkbox>
    ) : null}

    {gapAcceptance === null ? null : (
      <GapAcceptanceFields acceptance={gapAcceptance} decisions={decisions} disabled={disabled} onChange={onChange} />
    )}
  </div>
);
