import type { ReactNode } from "react";

/* What the screen is for at this moment. `read` is the workspace: the draft's lines, a
   section at a time, beside what the reader needs while deciding them. `document` is the
   whole rendered document, with its template and its check. */
export type DraftWorkspaceMode = "read" | "document";

interface DraftWorkspaceProps {
  /* The lines and everything kept beside them. */
  editor: ReactNode;
  /* Chosen by `DraftPreviewToggle` in the heading; switching to `document` settles the
     autosave buffer first, which is the page's business rather than the layout's. */
  mode: DraftWorkspaceMode;
  preview: ReactNode;
}

/* One of the two at a time, at every width - the design keeps the rendered document
   behind the heading's preview button rather than in a column beside the lines.

   Both stay mounted and one is hidden, rather than one being unmounted: switching modes
   must not discard text the reader has typed, and an unmounted editor would take its
   visible text with it. */
export const DraftWorkspace = ({ editor, mode, preview }: DraftWorkspaceProps) => (
  <>
    {/* `hidden` wins over `contents`: the preflight's rule for it is `!important`. */}
    <div className="contents" hidden={mode === "document"}>
      {editor}
    </div>
    <div className="flex min-w-0 flex-col gap-5" hidden={mode !== "document"}>
      {preview}
    </div>
  </>
);
