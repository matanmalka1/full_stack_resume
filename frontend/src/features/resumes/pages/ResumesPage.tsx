import { useQuery } from "@tanstack/react-query";
import { Download, FileText } from "lucide-react";
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { applicationListQueryOptions } from "@/api/applications";
import type { ApplicationListItem } from "@/api/contracts";
import { documentPdfHref, documentPreviewSrc } from "@/api/documents";
import { routePaths } from "@/navigation/routePaths";
import { buttonClasses } from "@/ui/Button";
import { DocumentFrame } from "@/ui/DocumentFrame";
import { EmptyState } from "@/ui/EmptyState";
import { SearchInput } from "@/ui/Input";
import { ListCard, ListRow } from "@/ui/ListCard";
import { LiveRegion } from "@/ui/LiveRegion";
import { PageShell } from "@/ui/PageShell";
import { QueryState } from "@/ui/QueryState";
import { Skeleton } from "@/ui/Skeleton";
import { useIsPhone } from "@/ui/useIsPhone";

/* Every Ready CV, newest first. Ready is the projection's own answer, so the server
   narrows the list; this screen only shows what it returned. */
const readyQuery = { stages: ["ready"] as const, sort: "updated" as const };

const resumesLoading = (
  <div className="flex flex-col gap-3">
    <LiveRegion>טוען את קורות החיים…</LiveRegion>
    <Skeleton className="block h-14 w-full" />
    <Skeleton className="block h-14 w-full" />
    <Skeleton className="block h-14 w-full" />
  </div>
);

const resumeLabel = (item: ApplicationListItem): string => `${item.company} · ${item.target_role}`;

/* A CV is found by its employer or its role. The whole Ready list is already here, so the
   field narrows it in place rather than asking the server again on every keystroke. */
const matchesQuery = (item: ApplicationListItem, query: string): boolean => {
  const needle = query.trim().toLocaleLowerCase();
  return needle === "" || `${item.company} ${item.target_role}`.toLocaleLowerCase().includes(needle);
};

/* The library of finished CVs: a list beside a preview of the chosen one. The preview is
   the document's current content composed on request, so it shows the same page the PDF
   carries. The chosen CV is in the address (`?application=`), so a link opens it. */
export const ResumesPage = () => {
  const isPhone = useIsPhone();
  const [searchParams, setSearchParams] = useSearchParams();
  const listQuery = useQuery(applicationListQueryOptions(readyQuery));
  const [query, setQuery] = useState("");
  const readyItems = (listQuery.data?.items ?? []).filter((item) => item.document_hash != null);
  const items = readyItems.filter((item) => matchesQuery(item, query));
  const requestedId = searchParams.get("application");
  const selected = items.find((item) => item.id === requestedId) ?? (isPhone ? undefined : items[0]);

  const select = (applicationId: string | null) => {
    const next = new URLSearchParams(searchParams);
    if (applicationId === null) next.delete("application");
    else next.set("application", applicationId);
    setSearchParams(next);
  };

  const list = (
    <div className={isPhone ? "flex w-full flex-col gap-3" : "flex w-80 shrink-0 flex-col gap-3 self-start"}>
      <label className="sr-only" htmlFor="resume-search">
        חיפוש קורות חיים
      </label>
      <SearchInput
        id="resume-search"
        onChange={(event) => setQuery(event.target.value)}
        placeholder="חיפוש לפי חברה או תפקיד"
        value={query}
      />
      {items.length === 0 ? (
        <p className="text-body text-cv-text-muted">לא נמצאו קורות חיים שתואמים לחיפוש.</p>
      ) : (
        <ListCard label="קורות חיים מוכנים">
          {items.map((item) => (
            <ListRow
              className={item.id === selected?.id ? "bg-cv-nav-active-bg font-bold" : undefined}
              icon={FileText}
              key={item.id}
              label={
                <span className="flex flex-col py-2 whitespace-normal">
                  <span>{item.company}</span>
                  <span className="text-label font-normal text-cv-text-muted">{item.target_role}</span>
                </span>
              }
              onClick={() => select(item.id)}
            />
          ))}
        </ListCard>
      )}
    </div>
  );

  const preview =
    selected === undefined || selected.document_hash == null ? null : (
      <section aria-label={`תצוגה מקדימה: ${resumeLabel(selected)}`} className="flex min-w-0 flex-1 flex-col gap-3">
        <div className="flex flex-wrap gap-2">
          <a
            className={buttonClasses("primary")}
            href={documentPdfHref(selected.id, selected.document_hash)}
          >
            <Download aria-hidden="true" className="size-icon-lg" />
            הורדת PDF
          </a>
          <Link className={buttonClasses("secondary")} to={routePaths.ready(selected.id)}>
            פתיחת המועמדות
          </Link>
          {isPhone ? (
            <button className={buttonClasses("ghost")} onClick={() => select(null)} type="button">
              חזרה לרשימה
            </button>
          ) : null}
        </div>
        <DocumentFrame
          className="w-full"
          key={selected.id}
          src={documentPreviewSrc(selected.id, selected.document_hash)}
          title={`קורות החיים: ${resumeLabel(selected)}`}
        />
      </section>
    );

  return (
    <PageShell description="כל קורות החיים שהכנתם הסתיימה, עם תצוגה מקדימה והורדה." title="כל קורות החיים">
      <QueryState
        error={listQuery.error}
        errorTitle="לא ניתן לטעון את קורות החיים"
        loading={listQuery.isPending}
        loadingState={resumesLoading}
        onRetry={() => void listQuery.refetch()}
      >
        {readyItems.length === 0 ? (
          <EmptyState>
            <p className="text-body text-cv-text-muted">עדיין אין קורות חיים מוכנים.</p>
          </EmptyState>
        ) : isPhone ? (
          (preview ?? list)
        ) : (
          <div className="flex items-start gap-6">
            {list}
            {preview}
          </div>
        )}
      </QueryState>
    </PageShell>
  );
};
