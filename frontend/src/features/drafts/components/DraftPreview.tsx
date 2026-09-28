import { useState } from "react";
import { CircleCheck, ExternalLink, FileText, RefreshCw } from "lucide-react";

import { documentPreviewPdfHref, documentPreviewSrc } from "@/api/documents";
import { buttonClasses } from "@/ui/Button";
import { DocumentFrame } from "@/ui/DocumentFrame";
import { LiveRegion } from "@/ui/LiveRegion";
import { StatusBadge } from "@/ui/StatusBadge";
import type { EditableDocument } from "../model/drafts.types";

/* A.4 frame 3's preview pane, and A.3's direction isolation.

   The frame is sandboxed without `allow-same-origin` and without `allow-scripts`, so the
   document renders in an opaque origin: it cannot script, cannot reach this page, and
   cannot fetch anything. The response carries the same refusal as a CSP, so neither side
   depends on the other remembering.

   It owns its own direction. The CV may be Hebrew, English, or mixed, and the RTL shell
   around it neither imposes nor inherits that - which is exactly why it is a document in
   a frame rather than markup rendered into this one.

   The URL is the document hash: a save produces a different URL and the frame navigates to a
   fresh document, so the preview cannot go on showing an edit that has been superseded.
   The frame itself is not remounted, so the reader's zoom survives the save. The frame
   never renders a PDF; the link beside the heading asks for one, on demand. */
export const DraftPreview = ({ draft }: { draft: EditableDocument }) => {
  /* Which version the frame has actually painted, rather than a flag an effect has to
     reset every time the version moves. A save gives the frame a new URL,
     so the version it last loaded is no longer the version on screen and the pane says it
     is refreshing - derived, with nothing to keep in step. `refreshed` is whether that
     load replaced an earlier one: the first paint is not news, a refresh after a save is. */
  const [loaded, setLoaded] = useState<{ refreshed: boolean; version: string } | null>(null);
  const loading = loaded?.version !== draft.document_hash;

  return (
    <section aria-labelledby="draft-preview-heading" className="flex flex-col gap-3">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex min-w-0 flex-col gap-1">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="flex items-center gap-2 text-heading-sm font-bold text-cv-text" id="draft-preview-heading">
              <FileText aria-hidden="true" className="size-icon-md text-cv-accent" />
              תצוגה מקדימה
            </h2>
            <StatusBadge tone="neutral">טיוטה</StatusBadge>
          </div>
          <span className="flex items-center gap-1.5 text-caption text-cv-text-muted">
            {loading ? (
              <RefreshCw aria-hidden="true" className="size-icon-sm animate-spin" />
            ) : (
              <CircleCheck aria-hidden="true" className="size-icon-sm" />
            )}
            {loading ? "מרענן את התצוגה…" : "מעודכן לגרסה השמורה"}
          </span>
          <LiveRegion>{!loading && loaded?.refreshed ? "התצוגה המקדימה עודכנה" : null}</LiveRegion>
        </div>
        {/* The real PDF of the saved version, before any approval: stamped as a draft,
            stored nowhere. Looking at the layout must not cost an approved version. */}
        <a
          className={buttonClasses("secondary", undefined, "compact")}
          href={documentPreviewPdfHref(draft.application_id, draft.document_hash)}
          rel="noopener noreferrer"
          target="_blank"
        >
          <ExternalLink aria-hidden="true" className="size-icon-md" />
          PDF הטיוטה
        </a>
      </header>

      {/* The frame owns its toolbar, canvas and page; nothing else sits between it and
          the document. */}
      <DocumentFrame
        busy={loading}
        className="w-full"
        onLoad={() => setLoaded((previous) => ({ refreshed: previous !== null, version: draft.document_hash }))}
        src={documentPreviewSrc(draft.application_id, draft.document_hash)}
        title="תצוגה מקדימה של הטיוטה"
      />

      <p className="text-caption text-cv-text-muted">
        נבנית בשרת מהתוכן השמור, באותו מסלול שמייצר את הקובץ הסופי. "PDF הטיוטה" פותח את הקובץ עם חותמת טיוטה, בלי
        אישור.
      </p>
    </section>
  );
};
