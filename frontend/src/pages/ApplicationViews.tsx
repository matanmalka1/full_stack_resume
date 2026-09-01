/* The two views of one Application, and the only way between them.

   The header above already names the company and the role, so this is not a second
   breadcrumb: it is the switch between the Application's two independent axes - what the
   document is doing and what the recruiter is doing. Both keep the same context, so
   neither is a level below the other and neither is reached by a back gesture.

   It was a pair of links to two routes. It is now one route with a switch, because the
   two views were never two places: they shared the masthead, the projection read, the
   error handling, and this switch, and differed only in which panel sat under it. Two
   routes for that meant two screens to keep in step, and the second one drifted - it grew
   its own loading sentence and its own error title for the same failed request.

   The switch is `ViewSwitch`, the same control the editor's panes use, and for the same
   reason it gives there: buttons with `aria-pressed` and no tab/panel contract. The pair
   briefly carried `role="tablist"` without keeping the contract - no roving tabIndex, no
   arrow keys, no focus target under the panel - and a tablist in RTL is a standing bug
   besides, since right arrow means the previous tab. Two views of one screen are not
   tabs; only the control's shape ever suggested they were.

   The view still survives a reload and a bookmark: it is `?view=` on the Application's own
   URL rather than a path of its own. What it no longer survives is a back gesture, which
   is the point - switching axis is not navigation, and it used to push a history entry
   that made "back" mean "the other tab" instead of "the list". */
export const applicationViews = [
  { label: "הכנת קורות החיים", value: "preparation" },
  { label: "מעקב גיוס", value: "tracking" },
] as const;

export type ApplicationView = (typeof applicationViews)[number]["value"];

/* The parameter is the view's own name and an unknown value is not honoured: `?view=`
   is user-editable, and a typo must land on the Application rather than on a blank card. */
export const applicationViewFromParam = (value: string | null): ApplicationView =>
  value === "tracking" ? "tracking" : "preparation";
