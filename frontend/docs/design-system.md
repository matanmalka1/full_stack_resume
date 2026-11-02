# Frontend design system

`src/styles.css` is the executable source of truth. This document records how its
tokens are intended to be used; component code must not copy raw values from it.

## Colour and themes

Private primitives use the `--cv-{family}-{step}` form and hold their light and dark
values once through `light-dark()`. Semantic colours exposed to
Tailwind use `--color-cv-{role}`. Components consume semantic utilities such as
`bg-cv-surface` and never primitives or Tailwind palette colours.

The palette is deliberately monochrome: white surfaces stand on a light grey canvas
(`#f1f3f5`), platinum and bright snow fill tracks and fields, while gunmetal and carbon
black carry text, actions and the dark theme. Dark keeps the same relation - the canvas
one step below the surface - rather than inverting it. The
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
| `hairline` | The edge of a surface: a card, the sidebar, a divider inside a card |
| `border`, `border-strong` | The edge of a control; `border-strong` for an outlined button or an attention chip |
| `border-soft` | A sheet's grab handle and an empty state's dashed frame |
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

Heebo is the primary Hebrew and Latin family. The scale: `caption` 12px, `support` 13px,
`label` 14px (field labels, legends, nav rows - drawn bold), `body` 15px,
`heading-sm` 16px, `heading-card` 17px (a card's own title), `heading-sheet` 20px (a
phone sheet's title), `heading-md` 22px (a dialog's title), and the route `h1` at
`title` 28px on a phone and `display` 32px from the large breakpoint, extra-bold.
Small headings stay close to body size and gain hierarchy through weight, while route
headings make the large statement. The
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

## Radii

From the inside out: `item` 8px (a row in a list, a segment in a switch), `control-sm`
10px (the quick-search field, a switch's track, a compact button), `control` 12px (a
full-size button or field), `control-lg` 14px (a sheet's or an empty state's large
command), `surface` 16px (a card), `fab` 18px (the board's floating button), `dialog`
22px (a centred dialog), `sheet` 24px (a bottom sheet's top corners and an empty
state's dashed frame), and `pill` for chips and badges.

## Shell and surfaces

On desktop the application uses a 248px white sidebar on the RTL inline-start edge,
top to bottom: the brand (an accent square with a page mark, then "סביבת קורות החיים"),
the full-width "משרה חדשה" command, the quick switcher drawn as a search field that
names ⌘K, the three areas, and sign-out pinned to the foot. A nav row is icon then label;
the active one is a flat background step, a bold label and a 2px edge indicator. The
sidebar does not fold: the design has no rail, so there is no collapse control.

Below the large breakpoint the sidebar becomes a top bar of the brand and a round
search button. The three destinations move to a tab bar pinned to the bottom of the
viewport: icon over a short visible label, the active one marked by a pill behind its
icon and a bold label. The new-job command becomes a
floating button over the board, above the bottom bar; sign-out moves to the Settings
account card. The board's action hub becomes a dark accent frame around a light list
there. The bar's
height is `--cv-bottom-nav-height` (zero at the large breakpoint), and every other
bottom-pinned surface - `CommitBar`, a sticky `ActionBar`, the Settings save row, the
page's own bottom padding and scroll padding - stands on top of it by that height.

A single choice among a few visible options (the theme) uses `SegmentedControl`: native
radios in a fieldset, drawn as segments, rather than a pair of switches encoding three
states.

`Card` is the design's surface on every screen: white on the canvas, `rounded-surface`,
a hairline edge and the faint `shadow-surface`. `cardClasses` gives a list item or a link
that is a card the same look; `surfaceClasses` is the edge and radius alone. A region
inside a card separates itself with a hairline, not a second card.

The shared primitives draw the design's vocabulary, so a screen composes them rather
than restyling them:

- `Button` sizes: `default` 46px, `large` 52px, `compact` 40px; `secondary` is an
  outlined white button on `border-strong`.
- `StatusBadge` is a 12px bold pill; `variant` `soft` (tinted fill, the default),
  `solid` (accent fill, for the one chip that asks for the reader) or `outline`.
- `FilterChip` / `filterChipClasses` is a quick filter's pill with an optional count;
  `ChoiceChips` is a radio group drawn as pills, with an optional dashed second set.
- `SegmentedControl` and `ViewSwitch` are a grey track with a white, lifted segment.
- `ProgressSegments` is a run of equal segments for a CV's progress; `InitialTile` is
  an employer's initial on a soft square; `ListCard` and `ListRow` are a card of rows
  divided by hairlines, a row that leads somewhere ending in a chevron.
- `EmptyState` is a dashed frame on the canvas, with no surface of its own.

Hover labels use the `Tooltip` component, never a native `title` attribute: the browser's
own tooltip arrives late, cannot be styled, and never shows on keyboard focus. Pass
`wrap` for a label longer than a control's name. Text that only repeats what is already
visible gets no tooltip; clamp it to two lines instead of truncating it.

Workflow routes draw their stage rail under the heading at desktop widths: one row of
24px marks in a white hairline card - a tick behind the work, a filled number for the
open stage, an outlined number ahead - joined by 2px connectors that are solid as far
as the work has come. The preparation steps (analysis, its matching settings, and the
verification step that creates the draft) share `StepFrame`: a 40px bordered back
square, the heading with role · company under it, the step's commands at the row's end,
then the rail. Below the large breakpoint a step gets the whole screen: the masthead and
bottom bar fold away (`--cv-bottom-nav-height` is the home-indicator inset alone there)
and the header becomes the step's compact header - back chevron, role over company -
then the open stage's name and position over one segment per stage, with the step's
commands in a `PhoneActionBar` on the bottom edge. The page heading stays in the
document for assistive tech unless the screen shows it (`phoneHeading`). The new-job
screen has no record yet: it draws a close mark and the draft's saved state over its
heading, and a numbered stepper (three short names on a phone, the four stage names
wide). The rail stays one navigation landmark, and every step keeps its accessible
name.

### Phone surfaces

The mobile design draws its own rules below the large breakpoint, all on the same
components through `max-lg:` utilities - never a second tree, which would double every
name a test or a screen reader finds:

- List screens (the board, the facts pool, Settings) draw their groups as rounded
  white cards on the canvas under plain labels.
  A filter used often becomes chips; the rest fold behind a "סינון" toggle that counts
  the active ones. A list and its record are two views chosen by the URL, and the
  record's one command is pinned above the bottom bar.
- `Dialog` is a bottom sheet (`presentation="sheet"`, the default): grab handle,
  `rounded-t-sheet`, an X, safe-area inset, and its commands on a hairline-topped bar.
  A two-answer question is a centred card (`presentation="alert"`, and always for
  `ConfirmDialog`) with an icon tile. From the large breakpoint every dialog is a
  centred `rounded-dialog` card with 28px padding and no dividers; an alert keeps its
  icon tile and draws no X there either. A footer
  splits its commands into halves or stacks them (`footerLayout`). A record menu becomes
  an action sheet, and the quick switcher is full screen.
- `CommitBar` and a sticky `ActionBar` run edge to edge on the bottom bar with 48px
  commands; `CommitBar` takes a `secondary` beside its primary and can drop `back`.
  Folded reference material is a `Disclosure variant="card"` row with a 56px summary.
- A run that is a step's whole body (`OperationOverlay`'s `screen`) is the screen at
  every width: a turning ring round the AI mark, the run's heading as the route
  heading, its four phases (sent, queued, running, done) stacked in a card on a phone
  and in columns on a wide screen, and the way back to the board and cancel - in the
  phone's bottom bar, under the card wide, where the run is one centred card. A run
  that ended without a result is reported in the same place: warning mark, the
  catalogue's title, what happened, that the prior state was kept, the phases with the
  failed one marked, and the ways on (Settings when a provider is missing, back to the
  application, the run again). Elsewhere a failure is a page in the report sheet.
- The application screen opens on the recruitment stage card and the dark next-action
  card at every width; the draft step opens with the job-fit card. On phones a draft's
  sections are cards under a pinned segmented strip of anchors - every section stays
  mounted - and a claim's edit and remove are labelled pills.
- Every touch target is at least 44px.

Route frames are centred in the content column, as the design draws them: 70rem for a
listing or record, 55rem for a page of settings or inputs (`measure="form"`), 51.25rem
for a single-question step (`measure="wizard"`). The gutter is 16px on a phone and 40px
beside the sidebar. The page heading stands on the canvas with no rule under it. Top-level areas
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

Shadows follow the same progression: `surface` (a card's faint lift), `segment` (the
selected segment of a switch), `action` (a large primary command), `fab`, `floating`,
`overlay` (a centred dialog), `sheet` (a bottom sheet, cast upwards), `document`.
Dark shadows combine a faint light edge with a black drop so adjacent dark surfaces
remain distinguishable.
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
tokens, arbitrary `rounded-[…]` and `shadow-[…]` values, focus-outline removal and
numeric z-index utilities.
