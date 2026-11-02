import { Check } from "lucide-react";
import type { FormEventHandler } from "react";
import type { UseFormReturn } from "react-hook-form";

import type { ApplicationDetail, TransitionableRecruitmentStatus } from "@/api/contracts";
import { ErrorCallout } from "@/ui/ErrorCallout";
import { Callout } from "@/ui/Callout";
import { Field } from "@/ui/Field";
import { Input, Textarea } from "@/ui/Input";
import { cx } from "@/ui/cx";
import { recruitmentStatusLabel, recruitmentStatuses } from "../model/recruitmentStatus";
import type { RecruitmentUpdateFields } from "../model/recruitment.types";

interface RecruitmentUpdateFormProps {
  detail: ApplicationDetail;
  fields: RecruitmentUpdateFields;
  form: UseFormReturn<RecruitmentUpdateFields>;
  inlineFields: ReadonlySet<string>;
  onSubmit: FormEventHandler<HTMLFormElement>;
  saveError: unknown;
  serverChanged: boolean;
  statusOptions: readonly TransitionableRecruitmentStatus[];
}

/* The statuses that end a process without an offer. They are drawn dashed, so ending the
   process is not one more step in the line of steps forward; on a phone they also sit in
   a row of their own under a rule. */
const endingStatuses: ReadonlySet<string> = new Set(["rejected", "withdrawn", "closed"]);

const chipClasses = (selected: boolean, ending: boolean) =>
  cx(
    "inline-flex min-h-11 cursor-pointer items-center gap-1.5 rounded-pill border px-3.5 text-label transition-colors has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-cv-focus lg:min-h-9.5",
    selected
      ? "border-cv-accent bg-cv-accent font-bold text-cv-on-accent"
      : cx(
          "text-cv-text hover:bg-cv-surface-muted",
          ending ? "border-dashed border-cv-border-strong" : "border-cv-border",
        ),
  );

const order = (status: string) => recruitmentStatuses.indexOf(status as (typeof recruitmentStatuses)[number]);

/* Every status the reader can move to as a chip, in the ladder's order, with the current
   one among them standing for "no change" - the form's empty value - and chosen until
   another is. Native radios underneath, so the group is one tab stop with arrow keys
   between chips. */
const StatusChips = ({
  current,
  onChange,
  options,
  value,
}: {
  current: string;
  onChange: (status: string) => void;
  options: readonly string[];
  value: string;
}) => {
  // ES2022 has no toSorted; this array is newly created and belongs only to this call.
  // oxlint-disable-next-line unicorn/no-array-sort
  const sorted = [current, ...options.filter((status) => status !== current)].sort(
    (left, right) => order(left) - order(right),
  );
  const chip = (status: string) => {
    const chipValue = status === current ? "" : status;
    const selected = value === chipValue;
    return (
      <label className={chipClasses(selected, endingStatuses.has(status))} key={status}>
        <input
          checked={selected}
          className="sr-only"
          name="recruitment-status-chip"
          onChange={() => onChange(chipValue)}
          type="radio"
          value={chipValue}
        />
        {selected ? <Check aria-hidden="true" className="size-icon-sm" /> : null}
        {recruitmentStatusLabel(status)}
        {chipValue === "" ? <span className="sr-only"> · המצב הנוכחי, ללא שינוי</span> : null}
      </label>
    );
  };
  const forward = sorted.filter((status) => !endingStatuses.has(status));
  const ending = sorted.filter((status) => endingStatuses.has(status));

  return (
    <fieldset className="flex flex-col">
      <legend className="mb-2.5 text-label font-bold text-cv-text">מצב המועמדות</legend>
      <div className="flex flex-wrap gap-2">
        {forward.map(chip)}
        {ending.length === 0 ? null : (
          <div className="flex flex-wrap gap-2 max-lg:mt-0.5 max-lg:basis-full max-lg:border-t max-lg:border-cv-hairline max-lg:pt-2.5 lg:contents">
            {ending.map(chip)}
          </div>
        )}
      </div>
    </fieldset>
  );
};

/* The status sheet's form: where the application stands, the next thing to do and when,
   and the reader's notes - only what changed is sent. */
export const RecruitmentUpdateForm = ({
  detail,
  fields,
  form,
  inlineFields,
  onSubmit,
  saveError,
  serverChanged,
  statusOptions,
}: RecruitmentUpdateFormProps) => {
  const { errors } = form.formState;

  return (
    <form className="flex min-w-0 flex-col gap-5" id="recruitment-update-form" onSubmit={onSubmit}>
      {serverChanged ? (
        // role="status" is a Callout prop, not a DOM role; Callout already renders an
        // <output> for it.
        // oxlint-disable-next-line jsx-a11y/prefer-tag-over-role
        <Callout role="status" title="פרטי המועמדות השתנו בינתיים" tone="warning">
          הערכים שהקלדת נשארו בטופס. כדאי לבדוק אותם לפני השמירה.
        </Callout>
      ) : null}

      <div className="flex flex-col gap-3">
        <StatusChips
          current={detail.recruitment_status}
          onChange={(status) =>
            form.setValue("targetStatus", status as RecruitmentUpdateFields["targetStatus"], {
              shouldDirty: true,
              shouldValidate: errors.targetStatus !== undefined,
            })
          }
          options={statusOptions}
          value={fields.targetStatus}
        />
        {errors.targetStatus?.message === undefined ? null : (
          <p className="text-support font-medium text-cv-blocker">{errors.targetStatus.message}</p>
        )}
        {detail.allowed_recruitment_transitions.length === 0 ? (
          <p className="text-support text-cv-text-muted">אין מעבר קדימה זמין מהמצב הנוכחי.</p>
        ) : null}
        {fields.targetStatus === "" ? null : (
          <Field error={errors.reason?.message} label="סיבת השינוי">
            {(control) => <Input {...control} {...form.register("reason")} dir="auto" />}
          </Field>
        )}
      </div>

      <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_12rem]">
        <Field error={errors.nextAction?.message} label="הפעולה הבאה">
          {(control) => (
            <Input
              {...control}
              {...form.register("nextAction")}
              dir="auto"
              placeholder="מה צריך לקרות ומתי כדאי לטפל בו."
            />
          )}
        </Field>
        <Field error={errors.nextActionDate?.message} label={<span className="max-lg:sr-only">תאריך</span>}>
          {(control) => <Input {...control} {...form.register("nextActionDate")} className="ltr-island" type="date" />}
        </Field>
      </div>

      <Field error={errors.notes?.message} label="הערות">
        {(control) => (
          <Textarea
            {...control}
            {...form.register("notes")}
            className="min-h-22"
            dir="auto"
            placeholder="מידע שימושי לשיחה או למעקב הבא."
          />
        )}
      </Field>
      {saveError == null ? null : (
        <ErrorCallout
          error={saveError}
          inlineFields={inlineFields}
          fallbackDetail="ייתכן שחלק מהשינויים נשמרו. הערכים נטענו מחדש; יש לבדוק אותם לפני ניסיון נוסף."
          title="העדכון לא הושלם"
        />
      )}
    </form>
  );
};
