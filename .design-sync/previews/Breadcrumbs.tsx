import { Breadcrumbs } from "cv-application-frontend";

export const Default = () => (
  <div className="p-4">
    <Breadcrumbs
      items={[
        { label: "הגשות" },
        { label: "Google – Frontend Engineer" },
        { label: "ניתוח" },
      ]}
    />
  </div>
);

export const Short = () => (
  <div className="p-4">
    <Breadcrumbs
      items={[
        { label: "הגשות" },
        { label: "קורות חיים" },
      ]}
    />
  </div>
);
