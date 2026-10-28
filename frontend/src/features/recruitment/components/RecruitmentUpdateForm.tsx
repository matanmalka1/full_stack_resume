import { Check } from "lucide-react";
import { type FormEventHandler, type ReactNode, useId } from "react";
import type { UseFormReturn } from "react-hook-form";

import type { ApplicationDetail, TransitionableRecruitmentStatus } from "@/api/contracts";
import { ErrorCallout } from "@/ui/ErrorCallout";
import { Callout } from "@/ui/Callout";
import { Field } from "@/ui/Field";
import { Select } from "@/ui/Select";
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
  visible: boolean;
}

/* The statuses that end a process without an offer. On a phone they sit in a row of
   their own under a rule, drawn dashed, so ending the process is not one more step in
   the line of steps forward. */
const endingStatuses: ReadonlySet<string> = new Set(["rejected", "withdrawn", "closed"]);

const chipClasses = (selected: boolean, ending: boolean) =>
  cx(
    "inline-flex min-h-11 cursor-pointer items-center gap-1.5 rounded-pill border px-3.5 text-support transition-colors has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-cv-focus",
    selected
      ? "border-cv-accent bg-cv-accent font-bold text-cv-on-accent"
      : cx(
          "text-cv-text-muted hover:bg-cv-surface-muted",
          ending ? "border-dashed border-cv-border-strong" : "border-cv-border",
        ),
  );

/* The stage choice: every stage the reader can move to as a chip, after the current one,
   which stands for "no change" and is the one chosen until another is. Native radios
   underneath, so the group is one tab stop with arrow keys between chips.

   It is the control at every width. It began as the phone's form of a select, but the
   desktop design draws the same chips, and a select hid the choice behind a click while
   the chips set every stage out in reading order. Nothing is lost: the options are the
   select's own list, a choice the server no longer allows (kept after a refresh) still
   says so, and the field's error is drawn under the group and named as its description. */
const StatusChips = ({
  allowed,
  current,
  error,
  onChange,
  options,
  value,
}: {
  allowed: readonly string[];
  current: string;
  error: string | undefined;
  onChange: (status: string) => void;
  options: readonly string[];
  value: string;
}) => {
  const errorId = useId();
  const order = (status: string) => recruitmentStatuses.indexOf(status as (typeof recruitmentStatuses)[number]);
  // ES2022 has no toSorted; this array is newly created and belongs only to this call.
  // oxlint-disable-next-line unicorn/no-array-sort
  const sorted = [...options].sort((left, right) => order(left) - order(right));
  const chip = (status: string, chipValue: string) => {
    const selected = value === chipValue;
    return (
      <label className={chipClasses(selected, endingStatuses.has(status))} key={chipValue || "current"}>
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
        {chipValue !== "" && selected && !allowed.includes(chipValue) ? " · הבחירה שלך" : null}
      </label>
    );
  };
  const forward = sorted.filter((status) => !endingStatuses.has(status));
  const ending = sorted.filter((status) => endingStatuses.has(status));

  return (
    <fieldset aria-describedby={error === undefined ? undefined : errorId} className="flex flex-col gap-2.5">
      <legend className="mb-2.5 text-support font-bold text-cv-text">מצב המועמדות</legend>
      <div className="flex flex-wrap gap-2">
        {chip(current, "")}
        {forward.map((status) => chip(status, status))}
      </div>
      {ending.length === 0 ? null : (
        <div className="flex flex-wrap gap-2 border-t border-cv-hairline pt-2.5">
          {ending.map((status) => chip(status, status))}
        </div>
      )}
      {error === undefined ? null : (
        <p className="text-support font-medium text-cv-blocker" id={errorId}>
          {error}
        </p>
      )}
    </fieldset>
  );
};

/* One group of the update form: what it changes and its fields. The groups carry no
   cards or icon tiles at any width - inside a dialog they were boxes inside a box, which
   neither the phone nor the desktop design draws - and keep only their titles. */
const UpdateSection = ({
  children,
  description,
  title,
}: {
  children: ReactNode;
  description: string;
  title: string;
}) => (
  <section>
    <div className="mb-3 flex items-start gap-3">
      <div>
        <h3 className="font-semibold text-cv-text">{title}</h3>
        <p className="text-support text-cv-text-muted">{description}</p>
      </div>
    </div>
    {children}
  </section>
);

export const RecruitmentUpdateForm = ({
  detail,
  fields,
  form,
  inlineFields,
  onSubmit,
  saveError,
  serverChanged,
  statusOptions,
  visible,
}: RecruitmentUpdateFormProps) => {
  const selectedStatus = fields.targetStatus;
  const { errors } = form.formState;

  return (
    <form
      className={cx("min-w-0 flex-col gap-4", visible ? "flex" : "hidden", "lg:flex")}
      id="recruitment-update-form"
      onSubmit={onSubmit}
    >
      {serverChanged ? (
        // role="status" is a Callout prop, not a DOM role; Callout already renders an
        // <output> for it.
        // oxlint-disable-next-line jsx-a11y/prefer-tag-over-role
        <Callout role="status" title="פרטי המועמדות השתנו בינתיים" tone="warning">
          הערכים שהקלדת נשארו בטופס. כדאי לבדוק אותם לפני השמירה.
        </Callout>
      ) : null}

      <p className="text-support text-cv-text-muted">אפשר לעדכן רק את הפרטים שהשתנו ולהשאיר את היתר כפי שהם.</p>

      <UpdateSection description="עדכון ההתקדמות מול המעסיק." title="שלב בתהליך">
        <div className="flex flex-col gap-4">
          {detail.allowed_recruitment_transitions.length === 0 ? null : (
            <StatusChips
              allowed={detail.allowed_recruitment_transitions}
              current={detail.recruitment_status}
              error={errors.targetStatus?.message}
              onChange={(status) =>
                form.setValue("targetStatus", status as RecruitmentUpdateFields["targetStatus"], {
                  shouldDirty: true,
                  shouldValidate: errors.targetStatus !== undefined,
                })
              }
              options={statusOptions}
              value={fields.targetStatus}
            />
          )}
          {/* With nowhere to move, the stage is shown as the disabled select it always was,
              with the sentence under it saying why. */}
          {detail.allowed_recruitment_transitions.length === 0 ? (
            <Field error={errors.targetStatus?.message} label="עדכון שלב">
              {(control) => (
                <Select {...control} {...form.register("targetStatus")} disabled value={fields.targetStatus}>
                  <option value="">ללא שינוי בשלב</option>
                  {statusOptions.map((status) => (
                    <option key={status} value={status}>
                      {recruitmentStatusLabel(status)}
                      {status === selectedStatus ? " · הבחירה שלך" : ""}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
          ) : null}
          {detail.allowed_recruitment_transitions.length === 0 ? (
            <p className="text-support text-cv-text-muted">אין מעבר קדימה זמין מהמצב הנוכחי.</p>
          ) : null}
          {fields.targetStatus === "" ? null : (
            <Field error={errors.reason?.message} label="סיבת השינוי">
              {(control) => <Input {...control} {...form.register("reason")} />}
            </Field>
          )}
        </div>
      </UpdateSection>

      <UpdateSection description="מה צריך לקרות ומתי כדאי לטפל בו." title="הפעולה הבאה">
        <div className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_10rem]">
          <Field error={errors.nextAction?.message} label="הפעולה הבאה">
            {(control) => <Input {...control} {...form.register("nextAction")} dir="auto" />}
          </Field>
          <Field error={errors.nextActionDate?.message} label="תאריך יעד">
            {(control) => (
              <Input {...control} {...form.register("nextActionDate")} className="ltr-island" type="date" />
            )}
          </Field>
        </div>
      </UpdateSection>

      <UpdateSection description="מידע שימושי לשיחה או למעקב הבא." title="הערות">
        <Field error={errors.notes?.message} label="תוכן ההערה">
          {(control) => <Textarea {...control} {...form.register("notes")} className="min-h-28" dir="auto" />}
        </Field>
      </UpdateSection>
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
