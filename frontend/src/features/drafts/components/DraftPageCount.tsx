import { useEffect, useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { FileText, TriangleAlert } from "lucide-react";

import { documentPageCountQueryOptions } from "@/api/documents";
import { cx } from "@/ui/cx";
import { LtrText } from "@/ui/LtrText";
import { toneTextClasses } from "@/ui/tone";

/* How long the saved version must stay put before its pages are counted. Each count
   launches a browser on the server, and autosave saves every pause in typing, so the
   count waits for the edits to settle rather than following each save. */
export const PAGE_COUNT_SETTLE_MS = 2500;

/* The hash once it has stopped moving: the first one at once, every later one only after
   `PAGE_COUNT_SETTLE_MS` without another save. */
const useSettledHash = (hash: string): string => {
  const [settled, setSettled] = useState(hash);
  useEffect(() => {
    if (hash === settled) return;
    const timer = setTimeout(() => setSettled(hash), PAGE_COUNT_SETTLE_MS);
    return () => clearTimeout(timer);
  }, [hash, settled]);
  return settled;
};

/* The live page count beside the preview (product spec §10): the saved content measured
   the way the render will lay it out, against the Profile's limit, so an overflow shows
   while editing rather than when the approved document fails to render.

   It is a hint, not a gate: while a newer version waits to be counted the last count stays,
   muted; a count the server could not make, or a failed request, shows nothing. */
export const DraftPageCount = ({ applicationId, documentHash }: { applicationId: string; documentHash: string }) => {
  const settled = useSettledHash(documentHash);
  const { data, isPlaceholderData } = useQuery({
    ...documentPageCountQueryOptions(applicationId, settled),
    placeholderData: keepPreviousData,
  });

  if (data?.pages == null) return null;
  const { pages, maximum } = data;
  const over = maximum != null && pages > maximum;
  const pending = isPlaceholderData || settled !== documentHash;
  const Icon = over ? TriangleAlert : FileText;
  const spoken =
    maximum == null
      ? `${pages} עמודים`
      : `${pages} עמודים מתוך ${maximum} המותרים${over ? ", חורג ממגבלת העמודים" : ""}`;

  return (
    <span
      className={cx(
        "flex items-center gap-1.5 text-caption",
        over ? cx(toneTextClasses.warning, "font-semibold") : "text-cv-text-muted",
        pending && "opacity-60",
      )}
      data-testid="draft-page-count"
    >
      <Icon aria-hidden="true" className="size-icon-sm" />
      <span aria-hidden="true">
        {maximum == null ? (
          pages
        ) : (
          <LtrText>
            {pages} / {maximum}
          </LtrText>
        )}{" "}
        עמודים
      </span>
      <span className="sr-only">{spoken}</span>
    </span>
  );
};
