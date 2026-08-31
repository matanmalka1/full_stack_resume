import type { ClassificationDecisions } from "../../api/analyses";
import { Checkbox } from "../../ui/Checkbox";
import { Field } from "../../ui/Field";
import { Select } from "../../ui/Select";
import {
  emphasisLabels,
  languageLabels,
  optionsFrom,
  profileLabels,
  trackLabels,
} from "./analysisLabels";

/* Which control answers which review reason. A `Record` over exactly the codes this
   screen owns, so a review reason added to the backend falls through to being named as
   belonging elsewhere instead of quietly acquiring an unrelated control.

   This is presentation over codes the projection literally sends. Which reasons exist,
   and whether the action is available at all, stay the projection's answer. */
export const CLASSIFICATION_REASON = "MATERIAL_CLASSIFICATION_AMBIGUITY";

export const FIT_REASONS: Record<string, true> = {
  LOW_FIT_REQUIRES_ACCEPTANCE: true,
  HARD_GAP_REQUIRES_DECISION: true,
};

export const REVIEW_REASONS_THIS_SCREEN_OWNS: Record<string, true> = {
  [CLASSIFICATION_REASON]: true,
  ...FIT_REASONS,
};

export const emptyDecisions: ClassificationDecisions = {
  track_override: null,
  profile_override: null,
  emphasis_override: null,
  language_override: null,
  accept_low_fit: false,
};

/* The form's own rule, and the only one it keeps: an empty submission is not a
   submission. It is not a copy of the server's "the submitted decisions change nothing"
   refusal, which also fires when a set value equals one already recorded - that answer
   stays the server's and is presented as it arrives. */
export const hasDecision = (decisions: ClassificationDecisions): boolean =>
  decisions.accept_low_fit ||
  decisions.track_override != null ||
  decisions.profile_override != null ||
  decisions.emphasis_override != null ||
  decisions.language_override != null;

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

const OverrideField = <T extends string>({
  disabled,
  hint,
  label,
  labels,
  onSelect,
  value,
}: OverrideFieldProps<T>) => (
  <Field hint={hint} label={label}>
    {(control) => (
      <Select
        {...control}
        disabled={disabled}
        onChange={(event) =>
          onSelect(event.target.value === NO_OVERRIDE ? null : (event.target.value as T))
        }
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

interface ReviewDecisionFormProps {
  decisions: ClassificationDecisions;
  disabled: boolean;
  onChange: (decisions: ClassificationDecisions) => void;
  showClassification: boolean;
  showFit: boolean;
}

export const ReviewDecisionForm = ({
  decisions,
  disabled,
  onChange,
  showClassification,
  showFit,
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

    {showFit ? (
      <Checkbox
        checked={decisions.accept_low_fit}
        disabled={disabled}
        hint="אישור זה נרשם על הניתוח עצמו, ולכן הוא פותר גם התאמה נמוכה וגם פער חוסם."
        onChange={(event) => onChange({ ...decisions, accept_low_fit: event.target.checked })}
      >
        אני מאשר את ההתאמה ואת הפערים ומבקש להמשיך
      </Checkbox>
    ) : null}
  </div>
);
