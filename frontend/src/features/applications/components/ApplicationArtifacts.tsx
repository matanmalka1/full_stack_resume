import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { applicationArtifactsQueryOptions } from "@/api/artifacts";
import { Button } from "@/ui/Button";
import { Card } from "@/ui/Card";
import { EmptyState } from "@/ui/EmptyState";
import { QueryState } from "@/ui/QueryState";
import { SectionHeader } from "@/ui/SectionHeader";
import { ApplicationArtifactRow } from "./ApplicationArtifactRow";

/* How many records are shown before the rest wait behind a press. */
const INITIAL_VISIBLE = 3;

/* The engine's evidence for this Application: the AI provider responses it kept (§4 of the
   single-document decision narrows the artifact registry to them).

   The CV itself is not here. It is the Application's one document, delivered as a file from
   the ready step while the document is Ready; the Submissions keep what was actually sent.
   What is left is provenance - checkable on the same integrity terms, and not what the
   reader came for, so it sits in a quiet reference section. */
export const ApplicationArtifacts = ({ applicationId }: { applicationId: string }) => {
  const query = useQuery(applicationArtifactsQueryOptions(applicationId));
  const [showAll, setShowAll] = useState(false);
  /* Newest first, which is the order the reader is asking about. The server's answer is
     never narrowed here - the rest is behind a press, not filtered away. */
  const ordered = [...(query.data?.items ?? [])]
    // The copied array is safe to mutate; the runtime target is ES2022.
    // oxlint-disable-next-line unicorn/no-array-sort
    .sort((left, right) => right.created_at.localeCompare(left.created_at));
  const visible = showAll ? ordered : ordered.slice(0, INITIAL_VISIBLE);
  const hiddenCount = ordered.length - visible.length;

  return (
    <Card aria-labelledby="artifacts-heading" className="rounded-surface bg-cv-surface p-4 shadow-surface sm:p-5">
      <SectionHeader
        align="baseline"
        description="כל קריאה ל־AI בתהליך נשמרת כאן: איזה שלב היא שירתה, באיזה מודל ומתי. אפשר לבדוק שהקובץ שנשמר לא השתנה ולהוריד אותו."
        gap="wide-compact"
        headingId="artifacts-heading"
        headingSize="body"
        spacing="compact"
        title="תוצרי המנוע"
      />

      <QueryState
        className="mt-3"
        empty={ordered.length === 0}
        emptyState={
          <EmptyState>
            <p className="text-support text-cv-text-muted">עוד לא נשמרה תשובת ספק למועמדות הזו.</p>
          </EmptyState>
        }
        error={query.error}
        errorDetail="אפשר לרענן את העמוד ולנסות שוב."
        errorTitle="לא ניתן לטעון את תוצרי המנוע"
        loading={query.isPending}
        loadingLabel="טוען את תוצרי המנוע…"
      >
        <ul className="mt-4 divide-y divide-cv-border">
          {visible.map((artifact) => (
            <ApplicationArtifactRow artifact={artifact} key={artifact.id} />
          ))}
        </ul>
        {hiddenCount <= 0 && !showAll ? null : (
          <div className="mt-2">
            <Button
              aria-expanded={showAll}
              className="min-h-9 px-2.5"
              onClick={() => setShowAll((value) => !value)}
              variant="ghost"
            >
              {showAll ? "הסתרת הרשומות הקודמות" : `הצגת רשומות קודמות (${hiddenCount})`}
            </Button>
          </div>
        )}
      </QueryState>
    </Card>
  );
};
