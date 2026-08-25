import { type ChangeEvent, useId, useState } from "react";
import { Upload } from "lucide-react";

import { JOB_TEXT_MAX_BYTES } from "../api/applications";
import { LiveRegion } from "../ui/LiveRegion";
import { LtrText } from "../ui/LtrText";
import { buttonClasses } from "../ui/Button";
import { cx } from "../ui/cx";

interface JobTextFileFieldProps {
  onText: (text: string) => void;
}

const isLocalTextFile = (file: File): boolean =>
  file.type === "text/plain" || /\.txt$/i.test(file.name);

/* A.4 frame 1: choosing a `.txt` file reads it locally into the text area. Nothing is
   uploaded, and the component owns the whole local-read outcome - the refusals, the
   announcement, and the file name - so the form only ever receives text.

   It is an optional convenience for filling the job text, so it is presented as one
   compact control beside that field rather than as a form field of its own competing
   with the text it fills. */
export const JobTextFileField = ({ onText }: JobTextFileFieldProps) => {
  const inputId = useId();
  const [loadedFileName, setLoadedFileName] = useState<string | null>(null);
  const [error, setError] = useState<string | undefined>(undefined);

  const readLocalFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];

    if (file === undefined) {
      return;
    }

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
    <div className="flex flex-col items-start gap-2">
      {/* The visible control is the label, so the native file input can stay off screen
          without losing its accessible name or keyboard reachability. */}
      <label
        className={cx(buttonClasses("secondary"), "cursor-pointer font-medium")}
        htmlFor={inputId}
      >
        <Upload aria-hidden="true" className="size-4" />
        קריאת קובץ טקסט מהמחשב (לא חובה)
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
      <p className="text-support text-cv-text-muted" id={`${inputId}-hint`}>
        הקובץ נקרא בדפדפן וממלא את שדה טקסט המשרה. שום קובץ אינו נשלח לשרת.
      </p>

      {error === undefined ? null : (
        <p className="text-support font-medium text-cv-blocker">{error}</p>
      )}

      {loadedFileName === null ? null : (
        <LiveRegion className="text-support text-cv-text-muted" visuallyHidden={false}>
          הטקסט מהקובץ <LtrText>{loadedFileName}</LtrText> נטען לשדה טקסט המשרה.
        </LiveRegion>
      )}
    </div>
  );
};
