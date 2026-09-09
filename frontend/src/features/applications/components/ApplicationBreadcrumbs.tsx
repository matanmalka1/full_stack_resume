import { boardPath } from "@/app/boardReturn";
import { routePaths } from "@/app/routePaths";
import { Breadcrumbs, type BreadcrumbItem } from "@/ui/Breadcrumbs";
import { applicationLabel } from "../model/applicationPresentation";

type ApplicationBreadcrumbPage = "job" | "draft" | "revision";

interface ApplicationBreadcrumbsProps {
  applicationId?: string;
  company?: string;
  page: ApplicationBreadcrumbPage;
  revisionLabel?: string;
  targetRole?: string;
}

/* One hierarchy for every view of an Application. Keeping the labels and destinations
   here prevents the preparation and revision screens from quietly describing the same
   parent differently. Data-backed labels are shown only when both canonical values are
   available; loading never exposes the record id as user-facing content.

   There is no "הכנת קורות החיים" level any more. It named a screen that turned out to be
   the Application record itself under a second URL, so the editor and the revision screen
   drew two crumbs one after the other that led to the same address - a hierarchy claiming
   a depth the routes do not have. */
export const ApplicationBreadcrumbs = ({
  applicationId,
  company,
  page,
  revisionLabel = "גרסה מוכנה",
  targetRole,
}: ApplicationBreadcrumbsProps) => {
  /* The board as the reader left it, filters and all - not a bare board that answers a
     different question than the one they were asking when they opened this record. */
  const items: BreadcrumbItem[] = [{ label: "מועמדויות", to: boardPath() }];

  /* Drawn whether or not the id has arrived. The revision screen learns which Application
     it belongs to from the record it is fetching, so gating this level on the id made the
     trail two items deep during the load and three once it settled - a level appearing
     under the reader's pointer. Without an id it is a name rather than a destination,
     which is what `applicationLabel` already falls back to. */
  items.push({
    dir: "auto",
    label: applicationLabel(company, targetRole),
    ...(page === "job" || applicationId === undefined ? {} : { to: routePaths.application(applicationId) }),
  });

  if (page === "draft") {
    items.push({ label: "עורך טיוטה" });
  } else if (page === "revision") {
    items.push({ label: revisionLabel });
  }

  return <Breadcrumbs items={items} />;
};
