import { useQuery } from "@tanstack/react-query";
import { Sparkles } from "lucide-react";
import { useState } from "react";

import { artifactDownloadHref, artifactVersionQueryOptions } from "@/api/artifacts";
import type { ArtifactVersion } from "@/api/contracts";
import { ErrorCallout } from "@/ui/ErrorCallout";
import { Button, buttonClasses } from "@/ui/Button";
import { Callout } from "@/ui/Callout";
import { Disclosure } from "@/ui/Disclosure";
import { SummaryList, type SummaryItem } from "@/ui/SummaryList";
import { formatBytes } from "@/utils/formatBytes";
import { formatDateTime } from "@/utils/formatDateTime";
import { artifactTypeLabel, providerTaskLabel, unavailableReasonLabel } from "../model/artifactLabels";

const metadataValue = (value: unknown): string =>
  typeof value === "string" ? value : (JSON.stringify(value, null, 0) ?? "");

const metadataString = (metadata: Record<string, unknown>, key: string): string | undefined => {
  const value = metadata[key];
  return typeof value === "string" && value !== "" ? value : undefined;
};

/* Metadata keys the readable summary already answers. Everything else the record carries
   still reaches the technical list below, so nothing the registry kept is hidden. */
const summarizedMetadataKeys = new Set(["task", "provider", "model", "reasoning_effort"]);

/* One kept provider response. The row answers what a reader asks first - which step of
   the work it came from, which model, and when - and the details answer whether the file
   is intact. Identifiers, hashes and prompt provenance are evidence rather than reading
   matter, so they wait behind their own disclosure instead of leading the details. */
export const ApplicationArtifactRow = ({ artifact }: { artifact: ArtifactVersion }) => {
  const [open, setOpen] = useState(false);
  const detailQuery = useQuery({ ...artifactVersionQueryOptions(artifact.id), enabled: open });
  const detail = detailQuery.data;

  const task = metadataString(artifact.metadata, "task") ?? artifact.logical_name;
  const provider = metadataString(artifact.metadata, "provider");
  const model = metadataString(artifact.metadata, "model");
  const reasoningEffort = metadataString(artifact.metadata, "reasoning_effort");
  const title = providerTaskLabel(task) ?? artifactTypeLabel(artifact.artifact_type);
  const created = formatDateTime(artifact.created_at, "short");

  const summaryItems: SummaryItem[] = [
    ...(provider === undefined ? [] : [{ term: "ספק", value: provider, ltr: true }]),
    ...(model === undefined ? [] : [{ term: "מודל", value: model, ltr: true }]),
    ...(reasoningEffort === undefined ? [] : [{ term: "רמת חשיבה", value: reasoningEffort, ltr: true }]),
    { term: "נשמרה", value: created },
    ...(detail?.size == null ? [] : [{ term: "גודל", value: formatBytes(detail.size), ltr: true }]),
  ];

  const technicalItems: SummaryItem[] = [
    { term: "משימה", value: task, ltr: true },
    { term: "מזהה ארטיפקט", value: artifact.artifact_id, ltr: true },
    { term: "מזהה גרסה", value: artifact.id, ltr: true },
    { term: "מספר גרסה", value: artifact.version_number, ltr: true },
    { term: "שם לוגי", value: artifact.logical_name, ltr: true },
    { term: "סטטוס", value: artifact.lifecycle_status, ltr: true },
    { term: "חתימת תוכן", value: artifact.content_hash, ltr: true },
    ...(artifact.profile == null ? [] : [{ term: "פרופיל", value: artifact.profile, ltr: true }]),
    ...(artifact.track == null ? [] : [{ term: "מסלול", value: artifact.track, ltr: true }]),
    ...(artifact.emphasis == null ? [] : [{ term: "דגש", value: artifact.emphasis, ltr: true }]),
    ...(artifact.facts_version == null
      ? []
      : [{ term: "גרסת מאגר העובדות", value: artifact.facts_version, ltr: true }]),
    ...Object.entries(artifact.metadata)
      .filter(([key]) => !summarizedMetadataKeys.has(key))
      .map(([key, value]) => ({ term: key, value: metadataValue(value), ltr: true })),
  ];

  return (
    <li className="py-3 first:pt-0 last:pb-0">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <span className="inline-flex size-9 shrink-0 items-center justify-center rounded-control bg-cv-surface-muted text-cv-text-muted">
            <Sparkles aria-hidden="true" className="size-icon-md" />
          </span>
          <div className="min-w-0">
            <p className="font-medium text-cv-text" dir="auto">
              {title}
            </p>
            <p className="text-support text-cv-text-muted">
              {model === undefined ? (
                created
              ) : (
                <>
                  <bdi>{model}</bdi> · {created}
                </>
              )}
            </p>
          </div>
        </div>
        <Button
          aria-expanded={open}
          className="min-h-9 px-2.5"
          onClick={() => setOpen((value) => !value)}
          variant="ghost"
        >
          {open ? "סגירה" : "פרטים"}
        </Button>
      </div>

      {open ? (
        <div className="mt-3 flex flex-col gap-3 rounded-control bg-cv-surface-muted p-3 sm:p-4">
          {detailQuery.error === null ? null : (
            <ErrorCallout
              error={detailQuery.error}
              fallbackDetail="הקובץ והרשומה לא השתנו. אפשר לנסות שוב."
              title="בדיקת שלמות הקובץ לא הושלמה"
            />
          )}

          <SummaryList items={summaryItems} />

          {detail === undefined ? (
            detailQuery.error === null ? (
              <p className="text-support text-cv-text-muted">בודק את שלמות הקובץ…</p>
            ) : null
          ) : detail.downloadable ? (
            <Callout title="הקובץ שלם: התוכן תואם את החתימה שנשמרה" tone="success" />
          ) : (
            <Callout title="הקובץ הרשום אינו זמין להורדה" tone="blocker">
              {detail.unavailable_reason == null
                ? "הקובץ לא עבר את בדיקת השלמות."
                : unavailableReasonLabel(detail.unavailable_reason)}
            </Callout>
          )}

          {detail?.downloadable === true ? (
            <div>
              <a className={buttonClasses("secondary")} href={artifactDownloadHref(artifact.id)}>
                הורדת התשובה שנשמרה
              </a>
            </div>
          ) : null}

          <Disclosure summary="מזהים וחתימות">
            <SummaryList items={technicalItems} />
          </Disclosure>
        </div>
      ) : null}
    </li>
  );
};
