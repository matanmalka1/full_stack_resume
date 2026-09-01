/* The two user-facing sections of one Application. Recruitment belongs to the job
   detail rather than becoming a third peer beside the document workflow. */
export const applicationViews = [
  { label: "פרטי משרה", value: "details" },
  { label: "הכנת קורות החיים", value: "preparation" },
] as const;

export type ApplicationView = (typeof applicationViews)[number]["value"];
