import { type ChangeEvent, type DragEvent, useId, useState } from "react";
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
  const [dragging, setDragging] = useState(false);

  const readLocalFile = async (file: File | undefined) => {
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

  /* The row used to claim the presence of a drop area while offering only a button, so
     dropping a posting on it did what the browser does by default: navigate away from a
     form holding unsaved text. It now accepts the drop it looks like it accepts, through
     the same reader and the same refusals as the picker. */
  const onDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragging(false);
    void readLocalFile(event.dataTransfer.files[0]);
  };

  return (
    <div
      className={cx(
        "flex flex-col gap-3 rounded-control border border-dashed p-4 transition-colors duration-200 sm:flex-row sm:items-center",
        dragging ? "border-cv-accent bg-cv-accent-soft" : "border-cv-border-strong bg-cv-surface-muted",
      )}
      onDragEnter={(event) => {
        event.preventDefault();
        setDragging(true);
      }}
      onDragLeave={(event) => {
        /* Only the crossing that leaves the zone itself; moving between its children
           fires the same event and would flicker the state off and on. */
        if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
          setDragging(false);
        }
      }}
      onDragOver={(event) => {
        event.preventDefault();
      }}
      onDrop={onDrop}
    >
      <label className={cx(buttonClasses("secondary"), "shrink-0 cursor-pointer font-medium")} htmlFor={inputId}>
        <Upload aria-hidden="true" className="size-4" />
        טעינה מקובץ txt
      </label>
      <input
        accept=".txt,text/plain"
        aria-describedby={`${inputId}-hint`}
        aria-invalid={error === undefined ? undefined : true}
        className="sr-only"
        id={inputId}
        onChange={(event: ChangeEvent<HTMLInputElement>) => {
          void readLocalFile(event.target.files?.[0]);
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
          אפשר לטעון קובץ במקום להדביק, או לגרור אותו לכאן. הקובץ נקרא בדפדפן ואינו נשלח לשרת.
        </p>
      </div>
    </div>
  );
};
