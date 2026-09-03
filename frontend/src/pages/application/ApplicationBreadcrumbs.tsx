import { appRoutes } from "../../app/appRoutes";
import { Breadcrumbs, type BreadcrumbItem } from "../../ui/Breadcrumbs";

type ApplicationBreadcrumbPage = "job" | "preparation" | "draft" | "revision";

interface ApplicationBreadcrumbsProps {
  applicationId?: string;
  company?: string;
  page: ApplicationBreadcrumbPage;
  revisionLabel?: string;
  targetRole?: string;
}

const applicationLabel = (company?: string, targetRole?: string): string => {
  if (company !== undefined && targetRole !== undefined) {
    return `${company} – ${targetRole}`;
  }

  return "פרטי משרה";
};

/* One hierarchy for every view of an Application. Keeping the labels and destinations
   here prevents the preparation and revision screens from quietly describing the same
   parent differently. Data-backed labels are shown only when both canonical values are
   available; loading never exposes the record id as user-facing content. */
export const ApplicationBreadcrumbs = ({
  applicationId,
  company,
  page,
  revisionLabel = "גרסה מוכנה",
  targetRole,
}: ApplicationBreadcrumbsProps) => {
  const items: BreadcrumbItem[] = [{ label: "מועמדויות", to: appRoutes.home }];

  if (applicationId !== undefined) {
    items.push({
      dir: "auto",
      label: applicationLabel(company, targetRole),
      ...(page === "job" ? {} : { to: appRoutes.application(applicationId) }),
    });

    if (page === "draft" || page === "revision") {
      items.push({ label: "הכנת קורות החיים", to: appRoutes.preparation(applicationId) });
    } else if (page === "preparation") {
      items.push({ label: "הכנת קורות החיים" });
    }
  }

  if (page === "draft") {
    items.push({ label: "עורך טיוטה" });
  } else if (page === "revision") {
    items.push({ label: revisionLabel });
  }

  return <Breadcrumbs items={items} />;
};
