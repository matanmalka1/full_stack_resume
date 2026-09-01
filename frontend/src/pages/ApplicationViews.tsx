/* The two sections of one Application, and the only way between them.

   The header above already names the company and the role, so this is not a second
   breadcrumb: it is the switch between the Application's two independent axes - what the
   document is doing and what the recruiter is doing. Both keep the same context, so
   neither is a level below the other.

   They remain one route because they share the projection read and error handling. The
   navigation is links rather than a view switch because the changing heading, status,
   actions, and body make them separate user-facing contexts inside that route.

   The pair briefly carried `role="tablist"` without keeping that contract. It now uses
   ordinary links and `aria-current`, so it promises neither tab keyboard behavior nor a
   pressed-button relationship the two contexts do not have.

   The view still survives a reload and a bookmark: it is `?view=` on the Application's own
   URL rather than a path of its own. Link navigation uses `replace`, so Back still means
   the list rather than the other section. */
export const applicationViews = [
  { label: "הכנת קורות החיים", value: "preparation" },
  { label: "מעקב גיוס", value: "tracking" },
] as const;

export type ApplicationView = (typeof applicationViews)[number]["value"];

/* The parameter is the view's own name and an unknown value is not honoured: `?view=`
   is user-editable, and a typo must land on the Application rather than on a blank card. */
export const applicationViewFromParam = (value: string | null): ApplicationView =>
  value === "tracking" ? "tracking" : "preparation";
