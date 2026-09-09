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
  const items: BreadcrumbItem[] = [{ label: "מועמדויות", to: routePaths.home }];

  if (applicationId !== undefined) {
    items.push({
      dir: "auto",
      label: applicationLabel(company, targetRole),
      ...(page === "job" ? {} : { to: routePaths.application(applicationId) }),
    });

  }

  if (page === "draft") {
    items.push({ label: "עורך טיוטה" });
  } else if (page === "revision") {
    items.push({ label: revisionLabel });
  }

  return <Breadcrumbs items={items} />;
};
