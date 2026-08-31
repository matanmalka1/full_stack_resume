import { cx } from "../ui/cx";

/* The two views of one Application, and the only way between them.

   The header above already names the company and the role, so this is not a second
   breadcrumb: it is the switch between the Application's two independent axes - what the
   document is doing and what the recruiter is doing. Both keep the same context, so
   neither is a level below the other and neither is reached by a back gesture.

   It was a pair of links to two routes. It is now a tab contract over one route, because
   the two views were never two places: they shared the masthead, the projection read, the
   error handling, and this switch, and differed only in which panel sat under it. Two
   routes for that meant two screens to keep in step, and the second one drifted - it grew
   its own loading sentence and its own error title for the same failed request.

   The view still survives a reload and a bookmark: it is `?view=` on the Application's own
   URL rather than a path of its own. What it no longer survives is a back gesture, which
   is the point - switching axis is not navigation, and it used to push a history entry
   that made "back" mean "the other tab" instead of "the list". */
const views = [
  { key: "preparation", label: "הכנת קורות החיים" },
  { key: "tracking", label: "מעקב גיוס" },
] as const;

export type ApplicationView = (typeof views)[number]["key"];

/* The parameter is the view's own name and an unknown value is not honoured: `?view=`
   is user-editable, and a typo must land on the Application rather than on a blank card. */
export const applicationViewFromParam = (value: string | null): ApplicationView =>
  value === "tracking" ? "tracking" : "preparation";

export const ApplicationViews = ({
  current,
  onChange,
}: {
  current: ApplicationView;
  onChange: (view: ApplicationView) => void;
}) => (
  <div
    aria-label="תצוגות המועמדות"
    className="flex gap-1 border-b border-cv-border"
    role="tablist"
  >
    {views.map((view) => {
      const active = view.key === current;

      return (
        <button
          aria-controls={`application-view-${view.key}`}
          aria-selected={active}
          className={cx(
            "-mb-px inline-flex min-h-11 items-center border-b-2 px-4 py-2 text-support font-semibold transition-colors duration-200",
            active
              ? "border-cv-accent text-cv-accent"
              : "border-transparent text-cv-text-muted hover:border-cv-border-strong hover:text-cv-text",
          )}
          id={`application-view-tab-${view.key}`}
          key={view.key}
          onClick={() => onChange(view.key)}
          role="tab"
          type="button"
        >
          {view.label}
        </button>
      );
    })}
  </div>
);
