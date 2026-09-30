import { ListTodo, type LucideIcon, Milestone, NotebookPen } from "lucide-react";
import type { FormEventHandler, ReactNode } from "react";
import type { UseFormReturn } from "react-hook-form";

import type { ApplicationDetail, TransitionableRecruitmentStatus } from "@/api/contracts";
import { ErrorCallout } from "@/ui/ErrorCallout";
import { Callout } from "@/ui/Callout";
import { iconTileClasses } from "@/ui/SectionHeader";
import { Field } from "@/ui/Field";
import { Select } from "@/ui/Select";
import { Input, Textarea } from "@/ui/Input";
import { cx } from "@/ui/cx";
import { recruitmentStatusLabel } from "../model/recruitmentStatus";
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

/* One group of the update form: what it changes, under its icon, and its fields. */
const UpdateSection = ({
  children,
  description,
  icon: Icon,
  title,
}: {
  children: ReactNode;
  description: string;
  icon: LucideIcon;
  title: string;
}) => (
  <section className="rounded-surface border border-cv-border bg-cv-surface p-4 shadow-surface">
    <div className="mb-4 flex items-start gap-3">
      <span className={iconTileClasses}>
        <Icon aria-hidden="true" className="size-icon-md" />
      </span>
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

      <UpdateSection description="עדכון ההתקדמות מול המעסיק." icon={Milestone} title="שלב בתהליך">
        <div className="flex flex-col gap-4">
          <Field error={errors.targetStatus?.message} label="עדכון שלב">
            {(control) => (
              <Select
                {...control}
                {...form.register("targetStatus")}
                disabled={detail.allowed_recruitment_transitions.length === 0}
                value={fields.targetStatus}
              >
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

      <UpdateSection description="מה צריך לקרות ומתי כדאי לטפל בו." icon={ListTodo} title="הפעולה הבאה">
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

      <UpdateSection description="מידע שימושי לשיחה או למעקב הבא." icon={NotebookPen} title="הערות">
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
