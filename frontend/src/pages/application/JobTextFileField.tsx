import { type ChangeEvent, useId, useState } from "react";
import { Upload } from "lucide-react";

import { JOB_TEXT_MAX_BYTES } from "../../api/applications";
import { buttonClasses } from "../../ui/Button";
import { LiveRegion } from "../../ui/LiveRegion";
import { LtrText } from "../../ui/LtrText";
import { cx } from "../../ui/cx";

interface JobTextFileFieldProps {
  onText: (text: string) => void;
}

const isLocalTextFile = (file: File): boolean => file.type === "text/plain" || /\.txt$/i.test(file.name);

/* Shared by initial intake and later snapshot capture. The browser reads the local file;
   only the resulting text reaches the owning form. */
export const JobTextFileField = ({ onText }: JobTextFileFieldProps) => {
  const inputId = useId();
  const [loadedFileName, setLoadedFileName] = useState<string | null>(null);
  const [error, setError] = useState<string | undefined>(undefined);

  const readLocalFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];

    if (file === undefined) return;

    setLoadedFileName(null);

    if (!isLocalTextFile(file)) {
      setError("ניתן לבחור קובץ טקסט בלבד, עם סיומת txt.");
      return;
    }

    if (file.size > JOB_TEXT_MAX_BYTES) {
      setError("הקובץ גדול מדי. ניתן להדביק את הטקסט הרלוונטי ישירות לשדה שלמטה.");
      return;
    }

    try {
      const text = await file.text();
      setError(undefined);
      onText(text);
      setLoadedFileName(file.name);
    } catch {
      setError("קריאת הקובץ נכשלה. ניתן להדביק את הטקסט ידנית לשדה שלמטה.");
    }
  };

  return (
    <div className="flex flex-col gap-3 rounded-control bg-cv-surface-muted p-4 sm:flex-row sm:items-center">
      <label className={cx(buttonClasses("secondary"), "shrink-0 cursor-pointer font-medium")} htmlFor={inputId}>
        <Upload aria-hidden="true" className="size-4" />
        בחירת קובץ טקסט
      </label>
      <input
        accept=".txt,text/plain"
        aria-describedby={`${inputId}-hint`}
        aria-invalid={error === undefined ? undefined : true}
        className="sr-only"
        id={inputId}
        onChange={(event) => {
          void readLocalFile(event);
        }}
        type="file"
      />
      <div className="min-w-0 flex-1">
        {error !== undefined ? (
          <p className="text-support font-medium text-cv-blocker">{error}</p>
        ) : loadedFileName !== null ? (
          <LiveRegion className="text-support text-cv-text-muted" visuallyHidden={false}>
            הטקסט מהקובץ <LtrText>{loadedFileName}</LtrText> נטען לשדה טקסט המשרה.
          </LiveRegion>
        ) : null}
        <p
          className={cx(
            "text-support text-cv-text-muted",
            error === undefined && loadedFileName === null ? undefined : "sr-only",
          )}
          id={`${inputId}-hint`}
        >
          קובצי txt בלבד. הקובץ נקרא בדפדפן ואינו נשלח לשרת.
        </p>
      </div>
    </div>
  );
};
