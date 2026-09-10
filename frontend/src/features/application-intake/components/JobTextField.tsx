import { FileText } from "lucide-react";
import type { UseFormRegister } from "react-hook-form";

import { JOB_TEXT_MAX_BYTES } from "@/api/applications";
import { Field } from "@/ui/Field";
import { FormSection } from "@/ui/FormSection";
import { LtrText } from "@/ui/LtrText";
import { Textarea } from "@/ui/Input";
import { cx } from "@/ui/cx";
import { formatBytes } from "@/utils/formatBytes";
import { isJobTextWithinBudget, jobTextByteLength, type ApplicationIntakeFields } from "../model/applicationIntake";

const NOTICE_RATIO = 0.8;

interface JobTextFieldProps {
  error?: string;
  jobText: string;
  onInputChanged: () => void;
  register: UseFormRegister<ApplicationIntakeFields>;
}

export const JobTextField = ({ error, jobText, onInputChanged, register }: JobTextFieldProps) => {
  const byteLength = jobText.length * 4 < JOB_TEXT_MAX_BYTES * NOTICE_RATIO ? null : jobTextByteLength(jobText);
  const isNearLimit = byteLength !== null && byteLength >= JOB_TEXT_MAX_BYTES * NOTICE_RATIO;
  const isOverLimit = byteLength !== null && !isJobTextWithinBudget(jobText);
  const counter =
    jobText.length === 0 ? null : isNearLimit ? (
      <span aria-hidden="true" className={cx("font-medium", isOverLimit ? "text-cv-blocker" : "text-cv-warning")}>
        <LtrText>
          {formatBytes(byteLength ?? 0)} / {formatBytes(JOB_TEXT_MAX_BYTES)}
        </LtrText>{" "}
        {isOverLimit ? "— חורג מגודל התצלום המותר" : "מגודל התצלום המותר"}
      </span>
    ) : (
      <span aria-hidden="true" className="font-normal text-cv-text-muted">
        <LtrText>{jobText.length.toLocaleString("en-US")}</LtrText> תווים
      </span>
    );

  return (
    <FormSection
      description="הטקסט יישמר בתצלום המשרה בדיוק כפי שהוזן."
      divided={false}
      title={
        <span className="inline-flex items-center gap-2">
          <FileText aria-hidden="true" className="size-icon-md text-cv-accent" />
          תיאור המשרה
        </span>
      }
    >
      <Field
        error={error}
        label={
          <span className="flex w-full items-baseline justify-between gap-4">
            <span>טקסט המשרה</span>
            {counter}
          </span>
        }
      >
        {(control) => (
          <Textarea
            {...control}
            {...register("job_text", {
              onChange: onInputChanged,
              validate: {
                required: (value) => value.trim() !== "" || "יש להזין את טקסט המשרה.",
                withinBudget: (value) =>
                  isJobTextWithinBudget(value) || "טקסט המשרה חורג מהגודל המותר. יש לקצר אותו לפני יצירת המועמדות.",
              },
            })}
            className="rtl-placeholder h-64 max-h-[55vh]"
            dir="auto"
            placeholder="הדבק כאן את תיאור המשרה…"
          />
        )}
      </Field>
    </FormSection>
  );
};
