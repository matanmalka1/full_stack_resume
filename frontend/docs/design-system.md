# Frontend design system

`src/styles.css` is the executable source of truth. This document records how its
tokens are intended to be used; component code must not copy raw values from it.

## Colour and themes

Private primitives use the `--cv-{family}-{step}` form and hold their light and dark
values once through `light-dark()`. Semantic colours exposed to
Tailwind use `--color-cv-{role}`. Components consume semantic utilities such as
`bg-cv-surface` and never primitives or Tailwind palette colours.

The palette is deliberately monochrome: bright snow and platinum establish the light
surfaces, while gunmetal and carbon black carry text, actions and the dark theme. The
two supplied pale-slate values are named `pale-slate-light` (`#ced4da`) and
`pale-slate` (`#adb5bd`) so both remain addressable without a duplicate token name.
Semantic status roles share this neutral family; their meaning therefore comes from
their Hebrew label, icon and structure rather than hue alone.

The theme is a server-owned setting (`ui_theme`: `system`, `light`, `dark`), read and
written through Settings like any other preference. `system` writes no attribute, so
changes to the operating-system preference keep applying live; an explicit choice stamps
`data-theme="light"` or `data-theme="dark"` on the root. Local storage holds only
`cv-theme-cache`, a startup cache so the first paint does not flash the wrong theme; it
is never authoritative. Both themes declare the matching `color-scheme`, allowing native controls to
follow the selected theme.

| Role | Purpose |
| --- | --- |
| `canvas`, `surface*` | Page and elevation hierarchy |
| `hairline` | Default separator for flat content regions |
| `nav-active*` | Flat navigation selection and its edge indicator |
| `text`, `text-muted` | Primary and supporting copy |
| `accent*` | Actions, selection, focus and active progress |
| `info*` | Informational messages that are not actions |
| `success*` | Completed or verified states |
| `warning*` | Attention required, without blocking |
| `blocker*` | Errors and states that prevent progress |

Light and dark text/status pairs are selected for WCAG AA at the sizes used by
`Callout` and `StatusBadge`. Recheck both schemes when changing a primitive, opacity, or pairing.
Colour is never the only state signal: shared tones also provide a Hebrew label and
an icon.

## Typography and direction

Heebo is the primary Hebrew and Latin family. Body text is 15px; supporting text is
13px; headings are 16px, 22px and 36px. Small headings stay close to body size and
gain hierarchy through weight, while route headings make the large statement. The
product shell is RTL. Use `dir="auto"`
for user/backend prose and `.ltr-island` or `.mono-code` for URLs, identifiers,
filenames and code. Do not add tracking to Hebrew text.

## Spacing

The Tailwind spacing scale stays fixed at 4px. Semantic spacing is calculated from the
separate `--cv-spacing-unit`, so compact density changes named layout decisions without
silently resizing every raw `p-*`, `m-*`, `gap-*`, width or height utility. Route intent
is a second axis: work/list routes tighten semantic layout spacing, while workflow/focus
routes expand it. The user's comfortable/compact preference remains independent and
continues to affect both route types.

| Token / utility suffix | Value | Use |
| --- | ---: | --- |
| `control-gap` | 8px | Icon/label and compact control content |
| `field-gap` | 12px | Related fields or compact rows |
| `card-padding` | 16px | Default card interior |
| `section-gap` | 24px | Sections within a page or form |
| `page-gap` | 32px | Major route-level regions |

For example, prefer `p-card-padding` and `gap-section-gap` when the spacing expresses
one of these roles. Raw spacing remains appropriate for local optical adjustment.

## Shell and surfaces

On desktop the application uses a text-first navigation sidebar on the RTL inline-start
edge; smaller viewports collapse it back to a horizontal masthead. Active navigation is a
flat background step, a heavier label and a 2px edge indicator.

The reader can fold the desktop sidebar to an icon rail. The choice is a per-browser
convenience kept in local storage, not a Setting, and it never reaches the narrow
masthead. On the rail every control keeps its accessible name and gains a `Tooltip` with
`placement="rail"`, which hangs beside the trigger and opens across the page rather than
off the viewport edge.

`Card` is flat by default: one hairline, no radius and no effective surface shadow.
Use `surfaceClasses` only for genuinely floating UI such as dialogs, dropdowns and
popovers. A normal table, form section or content panel should separate itself with a
hairline or a background step, not border, radius and shadow together.

The application board is the one deliberate exception. Its table, its cards and its
stage lanes follow the `demo_re` reference board the product owner chose: the table is a
rounded (`rounded-surface`), shadowed card with a `canvas`-toned header, and each card
and stage lane is rounded as well. Because the table cannot clip its own corners - row
menus open over its edge - its header and last-row corner cells take the radius
themselves (`rounded-ss-surface` and its siblings). Other screens keep the flat default;
the exception does not extend to them by example.

Hover labels use the `Tooltip` component, never a native `title` attribute: the browser's
own tooltip arrives late, cannot be styled, and never shows on keyboard focus. Pass
`wrap` for a label longer than a control's name. Text that only repeats what is already
visible gets no tooltip; clamp it to two lines instead of truncating it.

Workflow routes place their stage spine beside the active content at desktop widths.
The spine uses heading-weight labels, larger marks and a continuous vertical connector;
below the large breakpoint it becomes one row of marks above the content, joined by
horizontal connectors, with only the open step labelled. It stays the same navigation
landmark, and every step keeps its accessible name.

Route frames start at the navigation edge rather than centring, so a page heading keeps
its position when moving between routes whatever the route's measure. Top-level areas
reached from the primary navigation carry no breadcrumb: the navigation already marks
where the reader is, and a trail through the board implied a hierarchy that does not
exist.

Inline `Callout` messages are compositions rather than chips: a coloured edge, icon,
sentence and adjacent resolution action on a transparent background. Soft filled
banners remain available only for a screen-level verdict. `StatusBadge` remains the
compact marker for dense lists, tables and small state summaries.

## Messages

Errors and confirmations have one wording pattern and one presentation, owned by
`ui/errorMessages.ts`, `ui/ErrorCallout.tsx` and `ui/SuccessNotice.tsx`.

**Wording.** A message says what happened and what the reader can do now, in short
Hebrew sentences:

- The title is the screen's and names what did not happen: `לא ניתן לטעון את …` for a
  read, `<the thing> לא <past verb>` for a command (`ההגדרות לא נשמרו`,
  `העובדה לא נמחקה`).
- The body is the catalogue's reason and action for a known Problem code, or the
  screen's fallback detail: what stayed as it was, then `אפשר לנסות שוב.` or the
  specific next step. `יש ל…` is for a required step; `אפשר ל…` for an optional one.
- The server's `title` and `detail`, Problem codes, HTTP statuses and exception text are
  never rendered. `reportError` writes them to the console (4xx as a warning, anything
  else as an error). Every code the API can return has a catalogue entry.

**Placement.**

- A field the server refused is marked under that field (`useServerFieldErrors`), with
  `aria-invalid` and focus on the first one. The form's summary callout leaves those
  fields out and lists only refusals it could not place.
- A command's error sits directly under the control row that sent it, or at the end of
  its form, just above the submit action.
- A failed read replaces or tops the region it was loading (`QueryState`).

**Presentation and timing.** Errors are a blocker `Callout` with `role="alert"`; they
stay until the command is retried or the region is reloaded. A success message is a
`SuccessNotice`: announced politely, never focused, and closed by its own button, the next
command, or a screen that has moved past it. Neither times out.

**When to confirm.** A success notice appears only when it tells the reader something the
screen does not already show - a consequence, a record kept elsewhere, or a result with no
other place on the page. A command whose effect is visible where it happened says nothing.

## Elevation and stacking

The z-index variables are ordinary root-level CSS tokens, not Tailwind theme namespaces.
Use them through Tailwind's custom-property syntax:

1. `z-(--cv-z-content-raised)` — marks above local tracks and sticky headings.
2. `z-(--cv-z-sticky)` — sticky action bars and local dropdowns.
3. `z-(--cv-z-navigation)` — the application header.
4. `z-(--cv-z-overlay)` — non-native overlay surfaces; native `<dialog>` uses the browser top layer.
5. `z-(--cv-z-toast)` — notifications that must remain visible above overlays.

Shadows follow the same progression: `surface`, `floating`, `overlay`, `document`.
Dark shadows combine a faint light edge with a black drop so adjacent dark surfaces
remain distinguishable. Ordinary content regions should use a hairline or a single
background shift; radius, border and shadow together are reserved for floating UI.
The token guard rejects numeric z-index utilities in component code.

## Icons

Lucide React is the only icon library. The semantic sizes are `size-icon-sm` (14px),
`size-icon-md` (16px), and `size-icon-lg` (20px). Use the default
`--stroke-icon: 2`; use `--stroke-icon-strong: 3` only for tiny affirmative marks
whose legibility requires it. Larger decorative or empty-state icons may use a local
size when their scale is intrinsic to that composition. Icons that do not convey new
text are `aria-hidden="true"`.

Large-text mode explicitly raises all three semantic icon sizes so controls keep their
visual balance with the enlarged labels.

## High contrast

In Windows forced-colours mode, skeleton gradients become bordered static regions,
the upcoming workflow connector becomes a dashed system-colour line, and soft status
surfaces retain a visible system-colour boundary. Meaning remains available through
text and icons rather than preserved author colours.

## Enforcement

`npm run lint:tokens` derives the available semantic colours, radii and shadows from
`@theme`. It rejects literal component colours, raw Tailwind palettes, unknown design
tokens, focus-outline removal and numeric z-index utilities.
