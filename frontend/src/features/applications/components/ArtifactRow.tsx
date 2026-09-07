import { useQuery } from "@tanstack/react-query";
import { File, FileCode2, FileText, type LucideIcon } from "lucide-react";
import { useState } from "react";

import { artifactDownloadHref, artifactVersionQueryOptions } from "@/api/artifacts";
import type { ArtifactVersion } from "@/api/contracts";
import { ErrorCallout } from "@/ui/ErrorCallout";
import { Button, buttonClasses } from "@/ui/Button";
import { Callout } from "@/ui/Callout";
import { SummaryList } from "@/ui/SummaryList";
import { formatBytes } from "@/ui/formatBytes";
import { formatDateTime } from "@/ui/formatDateTime";
import { artifactTypeLabel, lifecycleLabel, unavailableReasonLabel } from "./artifactLabels";

const artifactIcons: Record<string, LucideIcon> = {
  resume_html: FileCode2,
  resume_markdown: FileText,
  resume_pdf: FileText,
};

const metadataValue = (value: unknown): string =>
  typeof value === "string" ? value : (JSON.stringify(value, null, 0) ?? "");

export const ArtifactRow = ({ artifact }: { artifact: ArtifactVersion }) => {
  const [open, setOpen] = useState(false);
  const detailQuery = useQuery({ ...artifactVersionQueryOptions(artifact.id), enabled: open });
  const detail = detailQuery.data;
  const metadataEntries = Object.entries(artifact.metadata);
  const Icon = artifactIcons[artifact.artifact_type] ?? File;

  return (
    <li className="py-2.5 first:pt-0 last:pb-0">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <span className="inline-flex size-9 shrink-0 items-center justify-center rounded-control bg-cv-surface-muted text-cv-text-muted">
            <Icon aria-hidden="true" className="size-4" />
          </span>
          <div className="min-w-0">
            <p className="font-medium text-cv-text" dir="auto">
              {artifactTypeLabel(artifact.artifact_type)}
            </p>
            <p className="text-support text-cv-text-muted">
              {lifecycleLabel(artifact.lifecycle_status)} · {formatDateTime(artifact.created_at, "short")}
            </p>
          </div>
        </div>
        <Button
          aria-expanded={open}
          className="min-h-9 px-2.5"
          onClick={() => setOpen((value) => !value)}
          variant="ghost"
        >
          {open ? "סגירה" : "פרטים ושלמות"}
        </Button>
      </div>

      {open ? (
        <div className="mt-3 flex flex-col gap-3 border-t border-cv-border pt-3">
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
              { term: "גרסת ארטיפקט", value: artifact.version_number, ltr: true },
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
              ...metadataEntries.map(([key, value]) => ({ term: key, value: metadataValue(value), ltr: true })),
            ]}
          />

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
