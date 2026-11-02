import { ClipboardPaste } from "lucide-react";
import { useId, useState } from "react";
import type { UseFormRegister } from "react-hook-form";

import { JOB_TEXT_MAX_BYTES } from "@/api/applications";
import { LtrText } from "@/ui/LtrText";
import { Textarea } from "@/ui/Input";
import { cx } from "@/ui/cx";
import { formatBytes } from "@/utils/formatBytes";
import { isJobTextWithinBudget, JOB_TEXT_REQUIRED_MESSAGE, jobTextByteLength } from "@/features/application-detail";
import type { ApplicationIntakeFields } from "../model/applicationIntake";

const NOTICE_RATIO = 0.8;

interface JobTextFieldProps {
  error?: string;
  jobText: string;
  onInputChanged: (field: keyof ApplicationIntakeFields) => void;
  /* Puts text read from the clipboard into the field, as typing it would. */
  onPaste: (text: string) => void;
  register: UseFormRegister<ApplicationIntakeFields>;
}

/* The posting itself: one large paste target, the press that pastes into it, and a count
   under it that turns into the size budget as the text nears it. */
export const JobTextField = ({ error, jobText, onInputChanged, onPaste, register }: JobTextFieldProps) => {
  const id = useId();
  const [pasteFailed, setPasteFailed] = useState(false);
  const byteLength = jobText.length * 4 < JOB_TEXT_MAX_BYTES * NOTICE_RATIO ? null : jobTextByteLength(jobText);
  const isNearLimit = byteLength !== null && byteLength >= JOB_TEXT_MAX_BYTES * NOTICE_RATIO;
  const isOverLimit = byteLength !== null && !isJobTextWithinBudget(jobText);
  const counter = isNearLimit ? (
    <span className={cx("font-medium", isOverLimit ? "text-cv-blocker" : "text-cv-warning")}>
      <LtrText>
        {formatBytes(byteLength ?? 0)} / {formatBytes(JOB_TEXT_MAX_BYTES)}
      </LtrText>{" "}
      {isOverLimit ? "— חורג מהגודל המותר" : "מהגודל המותר"}
    </span>
  ) : (
    <span>
      <LtrText>{jobText.length.toLocaleString("en-US")}</LtrText> תווים
    </span>
  );

  /* The clipboard is the browser's to refuse - an unfocused page, a denied permission, an
     engine without the API. Refused, the press says so and leaves the field to the
     keyboard's own paste. */
  const paste = async () => {
    try {
      const text = await navigator.clipboard.readText();
      setPasteFailed(false);
      if (text !== "") onPaste(text);
    } catch {
      setPasteFailed(true);
    }
    document.getElementById(id)?.focus();
  };

  const pasteButton = (
    <button
      className="flex h-9.5 items-center gap-1.5 rounded-pill border border-cv-border bg-cv-surface px-3.5 text-support font-bold text-cv-text shadow-surface transition-colors hover:bg-cv-surface-muted"
      onClick={() => void paste()}
      type="button"
    >
      <ClipboardPaste aria-hidden="true" className="size-icon-md" />
      הדבקה
    </button>
  );

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between gap-3">
        <label className="text-label font-bold text-cv-text" htmlFor={id}>
          טקסט המודעה
        </label>
        <span className="max-lg:hidden">{pasteButton}</span>
      </div>
      <div className="relative">
        <Textarea
          aria-describedby={cx(`${id}-meta`, error === undefined ? undefined : `${id}-error`)}
          aria-invalid={error === undefined ? undefined : true}
          id={id}
          {...register("job_text", {
            onChange: () => onInputChanged("job_text"),
            validate: {
              required: (value) => value.trim() !== "" || JOB_TEXT_REQUIRED_MESSAGE,
              withinBudget: (value) =>
                isJobTextWithinBudget(value) || "טקסט המשרה חורג מהגודל המותר. יש לקצר אותו לפני יצירת המועמדות.",
            },
          })}
          className="rtl-placeholder h-65 resize-y border-dashed border-cv-border-strong max-lg:h-47.5 max-lg:resize-none max-lg:pb-14"
          dir="auto"
          placeholder="הדבק כאן את המודעה המלאה, כולל הדרישות והתיאור"
        />
        <span className="absolute start-2.5 bottom-2.5 lg:hidden">{pasteButton}</span>
      </div>
      <p className="flex justify-between gap-3 text-caption text-cv-text-muted" id={`${id}-meta`}>
        <span>{pasteFailed ? "הדפדפן לא אפשר הדבקה מכאן. אפשר להדביק ישירות בשדה." : "עברית או אנגלית"}</span>
        {counter}
      </p>
      {error === undefined ? null : (
        <p className="text-support font-medium text-cv-blocker" id={`${id}-error`}>
          {error}
        </p>
      )}
    </div>
  );
};
