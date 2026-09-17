import { SummaryList } from "cv-application-frontend";

export const Default = () => (
  <div className="p-4 max-w-lg">
    <SummaryList
      items={[
        { term: "חברה", value: "Google" },
        { term: "תפקיד", value: "Frontend Engineer" },
        { term: "מיקום", value: "תל אביב, ישראל" },
        { term: "סוג משרה", value: "Full-time" },
      ]}
    />
  </div>
);

export const WithLtr = () => (
  <div className="p-4 max-w-lg">
    <SummaryList
      items={[
        { term: "מזהה הגשה", value: "app-2024-0142", ltr: true },
        { term: "תאריך הגשה", value: "17 בספטמבר 2024", ltr: true },
        { term: "גרסת קורות חיים", value: "v3.2.1", ltr: true },
        { term: "סטטוס", value: "ממתין לאישור" },
      ]}
    />
  </div>
);
