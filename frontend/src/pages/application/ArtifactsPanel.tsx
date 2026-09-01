import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";

import {
  applicationArtifactsQueryOptions,
  artifactDownloadHref,
  artifactVersionQueryOptions,
} from "../../api/artifacts";
import type { ArtifactVersion } from "../../api/contracts";
import { ErrorCallout } from "../../app/ErrorCallout";
import { Button, buttonClasses } from "../../ui/Button";
import { Callout } from "../../ui/Callout";
import { LtrText } from "../../ui/LtrText";
import { SummaryList } from "../../ui/SummaryList";
import { formatDateTime } from "../../ui/formatDateTime";
import { artifactTypeLabel, isDeliverableArtifact, lifecycleLabel, unavailableReasonLabel } from "./artifactLabels";

const formatBytes = (size: number): string =>
  size < 1024
    ? `${size} B`
    : size < 1024 * 1024
      ? `${(size / 1024).toLocaleString("en-US", { maximumFractionDigits: 1 })} KB`
      : `${(size / (1024 * 1024)).toLocaleString("en-US", { maximumFractionDigits: 2 })} MB`;

/* Arbitrary registered metadata, rendered as it was stored. A nested value is serialized
   rather than flattened: this is a record of what the engine wrote, and reshaping it here
   would be a second opinion about a field only the writer understands. */
const metadataValue = (value: unknown): string =>
  typeof value === "string" ? value : (JSON.stringify(value, null, 0) ?? "");

/* One registered artifact, and the verification that says whether its bytes are still
   the bytes that were registered.

   The row opens rather than showing everything at once, and that is what makes the
   integrity answer honest. `downloadable` costs the same containment, presence, and hash
   verification the download runs, per artifact - so it is asked when the reader asks,
   and the answer is true of that moment rather than of whenever the screen was opened. */
const ArtifactRow = ({ artifact }: { artifact: ArtifactVersion }) => {
  const [open, setOpen] = useState(false);
  const detailQuery = useQuery({ ...artifactVersionQueryOptions(artifact.id), enabled: open });
  const detail = detailQuery.data;
  const metadataEntries = Object.entries(artifact.metadata);

  return (
    <li className="py-3 first:pt-0 last:pb-0">
      <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-2">
        <div className="min-w-0">
          <p className="font-medium text-cv-text" dir="auto">
            {artifactTypeLabel(artifact.artifact_type)}
          </p>
          <p className="mt-1 text-support text-cv-text-muted">
            גרסה <LtrText>{artifact.version_number}</LtrText> · {lifecycleLabel(artifact.lifecycle_status)} ·{" "}
            {formatDateTime(artifact.created_at, "short")}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button aria-expanded={open} onClick={() => setOpen(!open)} variant="ghost">
            {open ? "סגירת הפרטים" : "פרטים ושלמות"}
          </Button>
        </div>
      </div>

      {open ? (
        <div className="mt-4 flex flex-col gap-3 border-t border-cv-border pt-4">
          {detailQuery.error === null ? null : (
            <ErrorCallout
              error={detailQuery.error}
              fallbackDetail="הרשומה עצמה לא השתנתה; רק בדיקת השלמות לא הושלמה."
              fallbackTitle="לא ניתן לבדוק את שלמות הקובץ"
            />
          )}

          <SummaryList
            items={[
              { term: "מזהה ארטיפקט", value: artifact.artifact_id, ltr: true },
              { term: "מזהה גרסת ארטיפקט", value: artifact.id, ltr: true },
              { term: "שם לוגי", value: artifact.logical_name, ltr: true },
              { term: "חתימת תוכן", value: artifact.content_hash, ltr: true },
              ...(artifact.approved_at == null
                ? []
                : [{ term: "אושר", value: formatDateTime(artifact.approved_at, "short") }]),
              ...(artifact.submitted_at == null
                ? []
                : [{ term: "הוגש", value: formatDateTime(artifact.submitted_at, "short") }]),
              ...(artifact.profile == null ? [] : [{ term: "פרופיל", value: artifact.profile }]),
              ...(artifact.track == null ? [] : [{ term: "מסלול", value: artifact.track }]),
              ...(artifact.emphasis == null ? [] : [{ term: "דגש", value: artifact.emphasis }]),
              ...(artifact.facts_version == null
                ? []
                : [{ term: "גרסת מאגר העובדות", value: artifact.facts_version, ltr: true }]),
              ...(detail?.size == null ? [] : [{ term: "גודל", value: formatBytes(detail.size), ltr: true }]),
              ...metadataEntries.map(([key, value]) => ({
                term: key,
                value: metadataValue(value),
                ltr: true,
              })),
            ]}
          />

          {/* The verification's own answer, stated as a verification rather than as a
              button that is merely missing: a payload that moved or changed is a finding
              about an immutable record, and the reader has to be told which of the two
              it is. */}
          {detail === undefined ? (
            <p className="text-support text-cv-text-muted">בודק את שלמות הקובץ…</p>
          ) : detail.downloadable ? (
            <Callout title="הקובץ נבדק ותוכנו תואם את החתימה שנרשמה" tone="success" />
          ) : (
            <Callout title="הקובץ הרשום אינו זמין להורדה" tone="blocker">
              {detail.unavailable_reason == null
                ? "בדיקת השלמות נכשלה ולא נמסרה סיבה."
                : unavailableReasonLabel(detail.unavailable_reason)}
            </Callout>
          )}

          {/* The technical download, offered only when the verification passed. Delivery
              of a CV to a recruiter stays on the revision screen and its `recruiter-pdf`
              route; this hands over the exact registered bytes. */}
          {detail?.downloadable === true ? (
            <div>
              <a className={buttonClasses("secondary")} href={artifactDownloadHref(artifact.id)}>
                הורדת הקובץ הרשום
              </a>
            </div>
          ) : null}
        </div>
      ) : null}
    </li>
  );
};

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

const ArtifactGroupList = ({ artifacts }: { artifacts: ArtifactVersion[] }) => (
  <ul className="mt-4 flex flex-col gap-3">
    {groupArtifacts(artifacts).map((group) => (
      <li className="rounded-control border border-cv-border bg-cv-surface px-4" key={group.key}>
        {group.revisionId === null ? null : (
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-cv-border py-3">
            <div>
              <p className="text-support font-semibold text-cv-text">גרסת קורות חיים</p>
              <p className="text-support text-cv-text-muted">
                {formatDateTime(group.artifacts[0]?.created_at ?? "", "short")} ·{" "}
                {group.artifacts.length === 1 ? "קובץ אחד" : `${group.artifacts.length} קבצים`}
              </p>
            </div>
            <Link className={buttonClasses("ghost")} to={`/revisions/${encodeURIComponent(group.revisionId)}`}>
              מעבר לגרסה
            </Link>
          </div>
        )}
        <ul className="divide-y divide-cv-border">
          {group.artifacts.map((artifact) => (
            <ArtifactRow artifact={artifact} key={artifact.id} />
          ))}
        </ul>
      </li>
    ))}
  </ul>
);

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
  const ordered = [...(query.data?.items ?? [])].sort((left, right) => right.created_at.localeCompare(left.created_at));
  const deliverables = ordered.filter((artifact) => isDeliverableArtifact(artifact.artifact_type));
  const internal = ordered.filter((artifact) => !isDeliverableArtifact(artifact.artifact_type));

  /* Nothing is registered until the first render, and a heading over an empty list would
     be a section about files that do not exist yet. The failure is still reported: the
     list not loading is different from there being nothing in it. */
  if (query.error === null && ordered.length === 0) {
    return null;
  }

  return (
    <section aria-labelledby="artifacts-heading">
      <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-2 border-b border-cv-border pb-4">
        <div className="min-w-0">
          <h2 className="text-body font-semibold text-cv-text" id="artifacts-heading">
            גרסאות וקבצים
          </h2>
          <p className="mt-1 text-support leading-6 text-cv-text-muted">
            הקבצים שנרשמו למועמדות הזו. כל אחד מהם רשומה בלתי משתנה, ואפשר לבדוק את שלמותו ולהוריד אותו בדיוק כפי שנרשם.
          </p>
        </div>
      </div>

      {query.error === null ? null : (
        <ErrorCallout
          className="mt-4"
          error={query.error}
          fallbackDetail="שום קובץ לא השתנה. אפשר לרענן ולנסות שוב."
          fallbackTitle="לא ניתן לטעון את רשימת הקבצים"
        />
      )}

      {deliverables.length === 0 ? null : <ArtifactGroupList artifacts={deliverables} />}

      {internal.length === 0 ? null : (
        <div className="mt-4 flex flex-col gap-3">
          <div>
            <Button aria-expanded={showInternal} onClick={() => setShowInternal(!showInternal)} variant="ghost">
              {showInternal ? "הסתרת תוצרי המנוע" : `הצגת תוצרי המנוע (${internal.length})`}
            </Button>
          </div>
          {showInternal ? <ArtifactGroupList artifacts={internal} /> : null}
        </div>
      )}
    </section>
  );
};
