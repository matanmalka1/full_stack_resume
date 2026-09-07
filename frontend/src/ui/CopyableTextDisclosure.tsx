import { Copy } from "lucide-react";
import { useState } from "react";

import { Disclosure } from "./Disclosure";
import { IconButton } from "./IconButton";
import { surfaceClasses } from "./surface";

/* Long, copyable text that should stay collapsed until the reader asks for it.
   The caller owns all copy, while this component owns disclosure and clipboard feedback. */
export const CopyableTextDisclosure = ({
  emptyMessage,
  label,
  summary,
  text,
}: {
  emptyMessage: string;
  /* What the text is, in the accusative the copy control reads with: "העתקת {label}". */
  label: string;
  summary: string;
  text: string | null | undefined;
}) => {
  const [copyState, setCopyState] = useState<"idle" | "copied" | "failed">("idle");
  const sourceText = typeof text === "string" ? text : "";

  if (sourceText.trim() === "") {
    return <p className="text-support leading-6 text-cv-text-muted">{emptyMessage}</p>;
  }

  const copySourceText = async () => {
    try {
      await navigator.clipboard.writeText(sourceText);
      setCopyState("copied");
    } catch {
      setCopyState("failed");
    }
  };

  return (
    <Disclosure summary={summary}>
      <div className="mb-2 flex items-center justify-end gap-2">
        <span aria-live="polite" className="text-support text-cv-text-muted">
          {copyState === "copied" ? `${label} הועתק` : copyState === "failed" ? "לא ניתן להעתיק" : null}
        </span>
        <IconButton aria-label={`העתקת ${label}`} onClick={() => void copySourceText()} title={`העתקת ${label}`}>
          <Copy aria-hidden="true" className="size-5 shrink-0" />
        </IconButton>
      </div>
      {/* Preserve the supplied direction and line breaks. Cap long content so opening the
          disclosure does not push the rest of its screen an unreasonable distance. */}
      <blockquote
        className={surfaceClasses("max-h-96 overflow-y-auto bg-cv-surface-muted py-3 ps-4 pe-3 text-cv-text")}
        dir="auto"
      >
        <p className="max-w-[75ch] text-body leading-7 whitespace-pre-wrap">{sourceText}</p>
      </blockquote>
    </Disclosure>
  );
};
