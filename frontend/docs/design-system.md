# Frontend design system

`src/styles.css` is the executable source of truth. This document records how its
tokens are intended to be used; component code must not copy raw values from it.

## Colour and themes

Private primitives use the `--cv-{family}-{step}` form. Semantic colours exposed to
Tailwind use `--color-cv-{role}`. Components consume semantic utilities such as
`bg-cv-surface` and never primitives or Tailwind palette colours.

The default follows `prefers-color-scheme`. The navigation toggle writes an explicit
`data-theme="light"` or `data-theme="dark"` choice to the root and persists it under
`cv-theme` in local storage. Until the first selection there is no attribute, so changes
to the operating-system preference continue to apply. Both themes declare the matching
`color-scheme`, allowing native controls to follow the selected theme.

| Role | Purpose |
| --- | --- |
| `canvas`, `surface*` | Page and elevation hierarchy |
| `text`, `text-muted` | Primary and supporting copy |
| `accent*` | Actions, selection, focus and active progress |
| `info*` | Informational messages that are not actions |
| `success*` | Completed or verified states |
| `warning*` | Attention required, without blocking |
| `blocker*` | Errors and states that prevent progress |

Text/status pairs are selected for WCAG AA at the sizes used by `Callout` and
`StatusBadge`. Recheck both themes when changing a primitive, opacity, or pairing.
Colour is never the only state signal: shared tones also provide a Hebrew label and
an icon.

## Typography and direction

Heebo is the primary Hebrew and Latin family. Body text is 16px; supporting text is
14px; headings are 20px, 24px and 32px. The product shell is RTL. Use `dir="auto"`
for user/backend prose and `.ltr-island` or `.mono-code` for URLs, identifiers,
filenames and code. Do not add tracking to Hebrew text.

## Spacing

The mechanical Tailwind scale remains based on 4px. Repeated layout decisions use:

| Token / utility suffix | Value | Use |
| --- | ---: | --- |
| `control-gap` | 8px | Icon/label and compact control content |
| `field-gap` | 12px | Related fields or compact rows |
| `card-padding` | 16px | Default card interior |
| `section-gap` | 24px | Sections within a page or form |
| `page-gap` | 32px | Major route-level regions |

For example, prefer `p-card-padding` and `gap-section-gap` when the spacing expresses
one of these roles. Raw spacing remains appropriate for local optical adjustment.

## Elevation and stacking

Use only named z-index utilities:

1. `z-content-raised` — marks above local tracks and sticky headings.
2. `z-sticky` — sticky action bars and local dropdowns.
3. `z-navigation` — the application header.
4. `z-overlay` — modal dialogs and their overlay surface.

Shadows follow the same progression: `surface`, `floating`, `overlay`, `document`.
The token guard rejects numeric z-index utilities in component code.

## Icons

Lucide React is the only icon library. The semantic sizes are `size-icon-sm` (14px),
`size-icon-md` (16px), and `size-icon-lg` (20px). Use the default
`--stroke-icon: 2`; use `--stroke-icon-strong: 3` only for tiny affirmative marks
whose legibility requires it. Larger decorative or empty-state icons may use a local
size when their scale is intrinsic to that composition. Icons that do not convey new
text are `aria-hidden="true"`.

## Enforcement

`npm run lint:tokens` derives the available semantic colours, radii and shadows from
`@theme`. It rejects literal component colours, raw Tailwind palettes, unknown design
tokens, focus-outline removal and numeric z-index utilities.
