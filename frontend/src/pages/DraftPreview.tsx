import { useEffect, useState } from "react";

import type { WorkingDraft } from "../api/contracts";
import { draftPreviewSrc } from "../api/drafts";
import { LiveRegion } from "../ui/LiveRegion";
import { StatusBadge } from "../ui/StatusBadge";

/* A.4 frame 3's preview pane, and A.3's direction isolation.

   The frame is sandboxed without `allow-same-origin` and without `allow-scripts`, so the
   document renders in an opaque origin: it cannot script, cannot reach this page, and
   cannot fetch anything. The response carries the same refusal as a CSP, so neither side
   depends on the other remembering.

   It owns its own direction. The CV may be Hebrew, English, or mixed, and the RTL shell
   around it neither imposes nor inherits that - which is exactly why it is a document in
   a frame rather than markup rendered into this one.

   The `key` is the version: a save produces a different URL and a fresh document, so the
   preview cannot go on showing an edit that has been superseded. Nothing here renders a
   PDF. */
export const DraftPreview = ({ draft }: { draft: WorkingDraft }) => {
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
  }, [draft.edit_version]);

  return (
    <section aria-labelledby="draft-preview-heading" className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="text-heading-sm font-semibold text-cv-text" id="draft-preview-heading">
          תצוגה מקדימה
        </h2>
        <StatusBadge tone="neutral">טיוטה</StatusBadge>
        <span className="text-support text-cv-text-muted">
          {loading ? "מרענן את התצוגה…" : "מעודכן לגרסה השמורה"}
        </span>
        <LiveRegion>{loading ? null : "התצוגה המקדימה עודכנה"}</LiveRegion>
      </div>

      <p className="text-support leading-6 text-cv-text-muted">
        התצוגה נבנית בשרת מהגרסה השמורה של הטיוטה, באותו מסלול שמייצר את הקובץ המאושר. היא
        מתעדכנת אחרי כל שמירה ואינה מייצרת PDF.
      </p>

      <iframe
        className="h-[70vh] w-full rounded-surface border border-cv-border bg-cv-surface"
        key={draft.edit_version}
        onLoad={() => setLoading(false)}
        sandbox=""
        src={draftPreviewSrc(draft.id, draft.edit_version)}
        title="תצוגה מקדימה של הטיוטה"
      />
    </section>
  );
};
