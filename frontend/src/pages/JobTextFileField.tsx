import { type ChangeEvent, useState } from "react";

import { JOB_TEXT_MAX_BYTES } from "../api/applications";
import { Field } from "../ui/Field";
import { LiveRegion } from "../ui/LiveRegion";
import { LtrText } from "../ui/LtrText";

interface JobTextFileFieldProps {
  onText: (text: string) => void;
}

const isLocalTextFile = (file: File): boolean =>
  file.type === "text/plain" || /\.txt$/i.test(file.name);

/* A.4 frame 1: choosing a `.txt` file reads it locally into the text area. Nothing is
   uploaded, and the component owns the whole local-read outcome - the refusals, the
   announcement, and the file name - so the form only ever receives text. */
export const JobTextFileField = ({ onText }: JobTextFileFieldProps) => {
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
    <>
      <Field
        error={error}
        hint="הקובץ נקרא בדפדפן וממלא את שדה טקסט המשרה. שום קובץ אינו נשלח לשרת."
        label="קריאת קובץ טקסט מהמחשב (לא חובה)"
      >
        {(control) => (
          <input
            {...control}
            accept=".txt,text/plain"
            className="block w-full text-support text-cv-text file:me-3 file:min-h-11 file:rounded-control file:border file:border-cv-border-strong file:bg-cv-surface-muted file:px-4 file:text-support file:font-medium file:text-cv-text"
            onChange={(event) => {
              void readLocalFile(event);
            }}
            type="file"
          />
        )}
      </Field>

      {loadedFileName === null ? null : (
        <LiveRegion className="text-support text-cv-text-muted" visuallyHidden={false}>
          הטקסט מהקובץ <LtrText>{loadedFileName}</LtrText> נטען לשדה טקסט המשרה.
        </LiveRegion>
      )}
    </>
  );
};
