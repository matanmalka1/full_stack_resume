import { ListTodo, Milestone, NotebookPen } from "lucide-react";
import type { FormEventHandler } from "react";
import type { UseFormReturn } from "react-hook-form";

import type { ApplicationDetail, TransitionableRecruitmentStatus } from "@/api/contracts";
import { ErrorCallout } from "@/app/ErrorCallout";
import { Callout } from "@/ui/Callout";
import { Field } from "@/ui/Field";
import { Select } from "@/ui/Select";
import { TextArea, TextInput } from "@/ui/TextInput";
import { cx } from "@/ui/cx";
import { recruitmentStatusLabel } from "@/features/applications/model/applicationLabels";

export interface RecruitmentUpdateFields {
  nextAction: string;
  nextActionDate: string;
  notes: string;
  reason: string;
  targetStatus: TransitionableRecruitmentStatus | "";
}

interface RecruitmentUpdateFormProps {
  detail: ApplicationDetail;
  fields: RecruitmentUpdateFields;
  form: UseFormReturn<RecruitmentUpdateFields>;
  onSubmit: FormEventHandler<HTMLFormElement>;
  saveError: unknown;
  serverChanged: boolean;
  statusOptions: readonly TransitionableRecruitmentStatus[];
  visible: boolean;
}

const sectionIconClasses =
  "inline-flex size-9 shrink-0 items-center justify-center rounded-control bg-cv-accent-soft text-cv-accent";

export const RecruitmentUpdateForm = ({
  detail,
  fields,
  form,
  onSubmit,
  saveError,
  serverChanged,
  statusOptions,
  visible,
}: RecruitmentUpdateFormProps) => {
  const selectedStatus = fields.targetStatus;

  return (
    <form
      className={cx("min-w-0 flex-col gap-4", visible ? "flex" : "hidden", "lg:flex")}
      id="recruitment-update-form"
      onSubmit={onSubmit}
    >
      {saveError == null ? null : (
        <ErrorCallout
          error={saveError}
          fallbackDetail="ייתכן שחלק מהשינויים נשמרו. הערכים נטענו מחדש מהשרת; יש לבדוק אותם לפני ניסיון נוסף."
          fallbackTitle="לא ניתן להשלים את העדכון"
        />
      )}
      {serverChanged ? (
        <Callout role="status" title="פרטי המועמדות השתנו בשרת" tone="warning">
          הערכים שהקלדת נשמרו בטופס ולא הוחלפו. כדאי לבדוק אותם לפני השמירה.
        </Callout>
      ) : null}

      <p className="text-support text-cv-text-muted">אפשר לעדכן רק את הפרטים שהשתנו ולהשאיר את היתר כפי שהם.</p>

      <section className="rounded-surface border border-cv-border bg-cv-surface p-4 shadow-surface">
        <div className="mb-4 flex items-start gap-3">
          <span className={sectionIconClasses}>
            <Milestone aria-hidden="true" className="size-4" />
          </span>
          <div>
            <h3 className="font-semibold text-cv-text">שלב בתהליך</h3>
            <p className="text-support text-cv-text-muted">עדכון ההתקדמות מול המעסיק.</p>
          </div>
        </div>
        <div className="flex flex-col gap-4">
          <Field label="עדכון שלב">
            {(control) => (
              <Select {...control} {...form.register("targetStatus")} value={fields.targetStatus}>
                <option value="">ללא שינוי בשלב</option>
                {statusOptions.map((status) => (
                  <option key={status} value={status}>
                    {recruitmentStatusLabel(status)}
                    {status === selectedStatus && !detail.allowed_recruitment_transitions.includes(status)
                      ? " · הבחירה שלך"
                      : ""}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          {fields.targetStatus === "" ? null : (
            <Field label="סיבת השינוי">{(control) => <TextInput {...control} {...form.register("reason")} />}</Field>
          )}
        </div>
      </section>

      <section className="rounded-surface border border-cv-border bg-cv-surface p-4 shadow-surface">
        <div className="mb-4 flex items-start gap-3">
          <span className={sectionIconClasses}>
            <ListTodo aria-hidden="true" className="size-4" />
          </span>
          <div>
            <h3 className="font-semibold text-cv-text">הפעולה הבאה</h3>
            <p className="text-support text-cv-text-muted">מה צריך לקרות ומתי כדאי לטפל בו.</p>
          </div>
        </div>
        <div className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_10rem]">
          <Field label="הפעולה הבאה">
            {(control) => <TextInput {...control} {...form.register("nextAction")} dir="auto" />}
          </Field>
          <Field label="תאריך יעד">
            {(control) => (
              <TextInput {...control} {...form.register("nextActionDate")} className="ltr-island" type="date" />
            )}
          </Field>
        </div>
      </section>

      <section className="rounded-surface border border-cv-border bg-cv-surface p-4 shadow-surface">
        <div className="mb-4 flex items-start gap-3">
          <span className={sectionIconClasses}>
            <NotebookPen aria-hidden="true" className="size-4" />
          </span>
          <div>
            <h3 className="font-semibold text-cv-text">הערות</h3>
            <p className="text-support text-cv-text-muted">מידע שימושי לשיחה או למעקב הבא.</p>
          </div>
        </div>
        <Field label="תוכן ההערה">
          {(control) => <TextArea {...control} {...form.register("notes")} className="min-h-28" dir="auto" />}
        </Field>
      </section>
    </form>
  );
};
