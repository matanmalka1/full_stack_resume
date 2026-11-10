import { useQuery } from "@tanstack/react-query";
import { ArrowUpLeft, BookOpen, Download, FileText, PencilLine, Plus } from "lucide-react";
import type { ReactNode } from "react";
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { applicationListQueryOptions } from "@/api/applications";
import type { ApplicationListItem } from "@/api/contracts";
import { documentPdfHref, documentPreviewSrc } from "@/api/documents";
import { preparationResumeDestination, preparationStateLabels } from "@/features/preparation";
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
import { StatusBadge } from "@/ui/StatusBadge";
import { cardClasses } from "@/ui/surface";
import { useIsPhone } from "@/ui/useIsPhone";
import { PreparationMeter } from "../components/PreparationMeter";
import { applicationAttention } from "../model/resumePresentation";

/* Every Application, newest first, in the endpoint's largest page. The product has no
   pager; a list past the server's own bound is far beyond its scale. */
const listQuery = { sort: "updated" as const, limit: 200 };

const resumesLoading = (
  <div className="flex flex-col gap-3">
    <LiveRegion>טוען את קורות החיים…</LiveRegion>
    <Skeleton className="block h-14 w-full" />
    <Skeleton className="block h-14 w-full" />
    <Skeleton className="block h-14 w-full" />
  </div>
);

const resumeLabel = (item: ApplicationListItem): string => `${item.company} · ${item.target_role}`;

/* A CV with a document to show: Ready, and its file composed. */
const isReady = (item: ApplicationListItem): boolean =>
  item.preparation_state === "ready" && item.document_hash != null;

/* A CV is found by its employer or its role. The whole list is already here, so the field
   narrows it in place rather than asking the server again on every keystroke. */
const matchesQuery = (item: ApplicationListItem, query: string): boolean => {
  const needle = query.trim().toLocaleLowerCase();
  return needle === "" || `${item.company} ${item.target_role}`.toLocaleLowerCase().includes(needle);
};

const AttentionBadge = () => (
  <StatusBadge icon={false} tone="progress" variant="soft">
    דורש טיפול
  </StatusBadge>
);

/* No Application exists yet: the offer to start one is the whole page - and, since a CV
   is built from the reader's facts, the way to fill those in first. */
const EmptyLibrary = () => (
  <EmptyState className="flex flex-col items-center justify-center max-lg:border-0 max-lg:px-3 max-lg:py-14 lg:min-h-[32rem]">
    <h2 className="text-heading-md font-extrabold text-cv-text lg:text-title">עוד אין קורות חיים</h2>
    <p className="mt-2 max-w-md text-body text-cv-text-muted">
      מדביקים מודעת משרה, והמערכת בונה ממנה קורות חיים מותאמים מתוך העובדות שלך.
    </p>
    <div className="mt-6 flex w-full flex-col items-center gap-3 lg:w-auto lg:flex-row lg:gap-2.5">
      <Link className={buttonClasses("primary", "w-full lg:w-auto", "large")} to={routePaths.newApplication}>
        <Plus aria-hidden="true" className="size-icon-md" />
        קליטת משרה ראשונה
      </Link>
      <Link className={buttonClasses("secondary", "w-full lg:w-auto")} to={routePaths.facts}>
        <BookOpen aria-hidden="true" className="size-icon-md" />
        קודם למלא את מאגר העובדות
      </Link>
    </div>
  </EmptyState>
);

/* A phone's top bar has no room for the new-job command, so there it floats above the
   bottom navigation, where a thumb reaches it. On a wide screen it is the sidebar's. */
const NewApplicationFab = () => (
  <>
    <div aria-hidden="true" className="h-16 lg:hidden" />
    <Link
      aria-label="קליטת משרה חדשה"
      className={buttonClasses(
        "primary",
        "fixed end-4 bottom-[calc(var(--cv-bottom-nav-height)+1rem)] z-(--cv-z-sticky) h-14 rounded-fab ps-4.5 pe-5 shadow-fab lg:hidden",
      )}
      to={routePaths.newApplication}
    >
      <Plus aria-hidden="true" className="size-icon-lg" />
      משרה חדשה
    </Link>
  </>
);

/* What a CV still in preparation shows where a Ready one shows its document: where it
   stands and what waits on the reader, if anything. */
const InProgressPanel = ({ item }: { item: ApplicationListItem }) => {
  const attention = applicationAttention(item);
  return (
    <div className={cardClasses("flex flex-col gap-4 p-5")}>
      <div className="flex items-center gap-2.5">
        <PreparationMeter item={item} />
      </div>
      <p className="text-body text-cv-text">{preparationStateLabels[item.preparation_state]}</p>
      {attention === null ? null : (
        <p className="flex flex-wrap items-center gap-2 text-body text-cv-text">
          <AttentionBadge />
          {attention}
        </p>
      )}
    </div>
  );
};

/* The chosen CV's head: whose it is on the start side, what to do with it on the end, so
   the commands sit on the document's edge rather than float above it. The main command
   comes last, at the far end. */
const DetailHeader = ({ actions, item }: { actions: ReactNode; item: ApplicationListItem }) => (
  <div className="flex flex-wrap items-end justify-between gap-x-4 gap-y-3">
    <div className="min-w-0">
      <h2 className="truncate text-heading-card font-extrabold text-cv-text">
        <bdi>{item.target_role}</bdi>
      </h2>
      <p className="truncate text-support text-cv-text-muted" dir="auto">
        {item.company}
      </p>
    </div>
    <div className="flex flex-wrap items-center gap-2">{actions}</div>
  </div>
);

/* The reader's CVs in one place: a list beside the chosen one. A Ready CV shows its
   document - composed on request, the same page the PDF carries - and its file; one still
   in preparation shows where it stands and the way on. The chosen CV is in the address
   (`?application=`), so a link, and every "back" from an Application, opens on it. */
export const ResumesPage = () => {
  const isPhone = useIsPhone();
  const [searchParams, setSearchParams] = useSearchParams();
  const list = useQuery(applicationListQueryOptions(listQuery));
  const [query, setQuery] = useState("");
  const allItems = list.data?.items ?? [];
  const items = allItems.filter((item) => matchesQuery(item, query));
  const inProgress = items.filter((item) => !isReady(item));
  const ready = items.filter(isReady);
  const requestedId = searchParams.get("application");
  /* Unasked, a wide screen opens on the newest Ready CV - its document is what this screen
     is for - and on the newest in preparation when nothing is Ready yet. */
  const selected =
    items.find((item) => item.id === requestedId) ?? (isPhone ? undefined : (ready[0] ?? inProgress[0]));

  const select = (applicationId: string | null) => {
    const next = new URLSearchParams(searchParams);
    if (applicationId === null) next.delete("application");
    else next.set("application", applicationId);
    setSearchParams(next);
  };

  const row = (item: ApplicationListItem) => (
    <ListRow
      className={item.id === selected?.id ? "bg-cv-nav-active-bg font-bold" : undefined}
      icon={isReady(item) ? FileText : PencilLine}
      key={item.id}
      label={
        <span className="flex flex-col py-2 whitespace-normal">
          <span>{item.company}</span>
          <span className="text-label font-normal text-cv-text-muted">{item.target_role}</span>
        </span>
      }
      onClick={() => select(item.id)}
      trailing={isReady(item) ? undefined : applicationAttention(item) !== null ? <AttentionBadge /> : "בהכנה"}
    />
  );

  const section = (title: string, sectionItems: ApplicationListItem[]) =>
    sectionItems.length === 0 ? null : (
      <section aria-label={title} className="flex flex-col gap-2">
        <h2 className="text-label font-bold text-cv-text-muted">
          {title} ({sectionItems.length})
        </h2>
        <ListCard>{sectionItems.map(row)}</ListCard>
      </section>
    );

  const listColumn = (
    <div className={isPhone ? "flex w-full flex-col gap-4" : "flex w-80 shrink-0 flex-col gap-4 self-start"}>
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
        <>
          {section("בהכנה", inProgress)}
          {section("מוכנים", ready)}
        </>
      )}
    </div>
  );

  const backToList = isPhone ? (
    <button className={buttonClasses("ghost", undefined, "compact")} onClick={() => select(null)} type="button">
      חזרה לרשימה
    </button>
  ) : null;

  const openApplication = (to: string) => (
    <Link className={buttonClasses("secondary", undefined, "compact")} to={to}>
      <ArrowUpLeft aria-hidden="true" className="size-icon-md" />
      פתיחת המועמדות
    </Link>
  );

  const detail =
    selected === undefined ? null : (
      <section aria-label={resumeLabel(selected)} className="flex min-w-0 flex-1 flex-col gap-4">
        {isReady(selected) && selected.document_hash != null ? (
          <>
            <DetailHeader
              actions={
                <>
                  {backToList}
                  {openApplication(routePaths.ready(selected.id))}
                  <a
                    className={buttonClasses("primary", undefined, "compact")}
                    href={documentPdfHref(selected.id, selected.document_hash)}
                  >
                    <Download aria-hidden="true" className="size-icon-md" />
                    הורדת PDF
                  </a>
                </>
              }
              item={selected}
            />
            <DocumentFrame
              className="w-full"
              key={selected.id}
              src={documentPreviewSrc(selected.id, selected.document_hash)}
              title={`קורות החיים: ${resumeLabel(selected)}`}
            />
          </>
        ) : (
          <>
            <DetailHeader
              actions={
                <>
                  {backToList}
                  {openApplication(routePaths.application(selected.id))}
                  <Link
                    className={buttonClasses("primary", undefined, "compact")}
                    to={preparationResumeDestination(selected)}
                  >
                    המשך הכנה
                  </Link>
                </>
              }
              item={selected}
            />
            <InProgressPanel item={selected} />
          </>
        )}
      </section>
    );

  return (
    <PageShell description="כל קורות החיים שלך: מה שמוכן להורדה ומה שעוד בהכנה." title="קורות החיים">
      <QueryState
        error={list.error}
        errorTitle="לא ניתן לטעון את קורות החיים"
        loading={list.isPending}
        loadingState={resumesLoading}
        onRetry={() => void list.refetch()}
      >
        {allItems.length === 0 ? (
          <EmptyLibrary />
        ) : (
          <>
            {isPhone ? (
              (detail ?? listColumn)
            ) : (
              <div className="flex items-start gap-6">
                {listColumn}
                {detail}
              </div>
            )}
            <NewApplicationFab />
          </>
        )}
      </QueryState>
    </PageShell>
  );
};
