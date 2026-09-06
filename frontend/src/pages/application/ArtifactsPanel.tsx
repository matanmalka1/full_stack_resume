import { useQuery } from "@tanstack/react-query";
import { Layers3 } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { applicationArtifactsQueryOptions } from "../../api/artifacts";
import type { ArtifactVersion } from "../../api/contracts";
import { appRoutes } from "../../app/appRoutes";
import { Button, buttonClasses } from "../../ui/Button";
import { Card } from "../../ui/Card";
import { QueryState } from "../../ui/QueryState";
import { SectionHeader } from "../../ui/SectionHeader";
import { formatDateTime } from "../../ui/formatDateTime";
import { ArtifactRow } from "./ArtifactRow";
import { artifactTypeLabel, isDeliverableArtifact } from "./artifactLabels";

interface ArtifactGroup {
  artifacts: ArtifactVersion[];
  key: string;
  revisionId: string | null;
}

const groupArtifacts = (artifacts: ArtifactVersion[]): ArtifactGroup[] => {
  const groups = new Map<string, ArtifactGroup>();

  for (const artifact of artifacts) {
    const revisionId = artifact.revision_id ?? null;
    const key = revisionId === null ? `artifact:${artifact.id}` : `revision:${revisionId}`;
    const group = groups.get(key);

    if (group === undefined) {
      groups.set(key, { artifacts: [artifact], key, revisionId });
    } else {
      group.artifacts.push(artifact);
    }
  }

  return [...groups.values()];
};

const fileCountLabel = (count: number): string => (count === 1 ? "קובץ אחד" : `${count} קבצים`);

const ArtifactGroupCard = ({ group, latest }: { group: ArtifactGroup; latest: boolean }) => {
  const [open, setOpen] = useState(false);
  const firstArtifact = group.artifacts[0];
  const title =
    group.revisionId === null
      ? artifactTypeLabel(firstArtifact?.artifact_type ?? "")
      : latest
        ? "הגרסה האחרונה"
        : "גרסה קודמת";

  return (
    <li className="rounded-control border border-cv-border bg-cv-surface">
      <div className="flex flex-wrap items-center justify-between gap-3 px-3 py-2.5 sm:px-4">
        <div className="flex min-w-0 items-center gap-3">
          <span className="inline-flex size-9 shrink-0 items-center justify-center rounded-control bg-cv-surface-muted text-cv-text-muted">
            <Layers3 aria-hidden="true" className="size-4" />
          </span>
          <div className="min-w-0">
            <p className="text-support font-semibold text-cv-text">{title}</p>
            <p className="text-support text-cv-text-muted">
              {formatDateTime(firstArtifact?.created_at ?? "", "short")} · {fileCountLabel(group.artifacts.length)}
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-1">
          {group.revisionId === null ? null : (
            <Link className={buttonClasses("ghost", "min-h-9 px-2.5")} to={appRoutes.revision(group.revisionId)}>
              פתיחת הגרסה
            </Link>
          )}
          <Button
            aria-expanded={open}
            className="min-h-9 px-2.5"
            onClick={() => setOpen((value) => !value)}
            variant="ghost"
          >
            {open ? "הסתרת הקבצים" : `הצגת הקבצים (${group.artifacts.length})`}
          </Button>
        </div>
      </div>
      {open ? (
        <ul className="mx-3 divide-y divide-cv-border border-t border-cv-border py-2 sm:mx-4">
          {group.artifacts.map((artifact) => (
            <ArtifactRow artifact={artifact} key={artifact.id} />
          ))}
        </ul>
      ) : null}
    </li>
  );
};

const ArtifactGroupList = ({ artifacts, internal = false }: { artifacts: ArtifactVersion[]; internal?: boolean }) => {
  const [showPrevious, setShowPrevious] = useState(false);
  const groups = groupArtifacts(artifacts);
  const visibleGroups = showPrevious ? groups : groups.slice(0, 1);
  const previousCount = groups.length - 1;

  return (
    <div className="mt-3 flex flex-col gap-2">
      <ul className="flex flex-col gap-2">
        {visibleGroups.map((group, index) => (
          <ArtifactGroupCard group={group} key={group.key} latest={index === 0} />
        ))}
      </ul>
      {previousCount === 0 ? null : (
        <div>
          <Button
            aria-expanded={showPrevious}
            className="min-h-9 px-2.5"
            onClick={() => setShowPrevious((value) => !value)}
            variant="ghost"
          >
            {showPrevious
              ? internal
                ? "הסתרת תוצרים קודמים"
                : "הסתרת גרסאות קודמות"
              : internal
                ? `הצגת תוצרים קודמים (${previousCount})`
                : `הצגת גרסאות קודמות (${previousCount})`}
          </Button>
        </div>
      )}
    </div>
  );
};

/* §14 of the product spec: the Application's own revisions-and-artifacts section, not a
   separate artifact manager.

   Everything it shows belongs to this Application and links back into it, which is why it
   is a region on this screen rather than a screen of its own: an artifact is meaningful
   as the output of a revision of this Application, and a global list of files would ask
   the reader to reconstruct that relationship from identifiers.

   The engine's own evidence - claim manifests, draft snapshots, provider responses - is
   here too, behind one press. It is part of the record and its integrity is checkable on
   the same terms; it is simply not what the reader came for. */
export const ArtifactsPanel = ({ applicationId }: { applicationId: string }) => {
  const query = useQuery(applicationArtifactsQueryOptions(applicationId));
  const [showInternal, setShowInternal] = useState(false);
  /* Newest first, which is the order the reader is asking about. The server's answer is
     never narrowed here - both groups below are rendered, one behind a press. */
  // Old records are immutable, but the retired render image is no longer part
  // of the product surface and must not reappear for historical revisions.
  const ordered = [...(query.data?.items ?? [])]
    .filter((artifact) => artifact.artifact_type !== "visual_evidence")
    .sort((left, right) => right.created_at.localeCompare(left.created_at));
  const deliverables = ordered.filter((artifact) => isDeliverableArtifact(artifact.artifact_type));
  const internal = ordered.filter((artifact) => !isDeliverableArtifact(artifact.artifact_type));

  /* Nothing is registered and nothing is loading, and a heading over an empty list would
     be a section about files that do not exist yet. Still loading is a different state
     from there being nothing in it - the panel stays visible below and reports that. */
  if (!query.isPending && query.error === null && ordered.length === 0) {
    return null;
  }

  return (
    <Card aria-labelledby="artifacts-heading" className="bg-cv-surface p-4 shadow-surface">
      <SectionHeader
        align="baseline"
        description="גרסאות קורות החיים והקבצים שנשמרו עבורן. פרטי שלמות זמינים לפי דרישה."
        gap="wide-compact"
        headingId="artifacts-heading"
        headingSize="body"
        spacing="compact"
        title="גרסאות וקבצים"
      />

      <QueryState
        className="mt-3"
        empty={ordered.length === 0}
        error={query.error}
        fallbackDetail="שום קובץ לא השתנה. אפשר לרענן ולנסות שוב."
        fallbackTitle="לא ניתן לטעון את רשימת הקבצים"
        loading={query.isPending}
        loadingLabel="טוען את רשימת הקבצים…"
      >
        {deliverables.length === 0 ? null : <ArtifactGroupList artifacts={deliverables} />}

        {internal.length === 0 ? null : (
          <div className="flex flex-col gap-3">
            <div>
              <Button aria-expanded={showInternal} onClick={() => setShowInternal(!showInternal)} variant="ghost">
                {showInternal ? "הסתרת תוצרי המנוע" : `הצגת תוצרי המנוע (${internal.length})`}
              </Button>
            </div>
            {showInternal ? <ArtifactGroupList artifacts={internal} internal /> : null}
          </div>
        )}
      </QueryState>
    </Card>
  );
};
