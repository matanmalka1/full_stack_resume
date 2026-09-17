# design-sync notes

## PKG_DIR resolution
When `--entry ./frontend/.ds-entry.ts` is passed, converter walks up from entry file dir
to find nearest `package.json` with a `name` field → `PKG_DIR = frontend/`.
All `cfg.*` path fields (`srcDir`, `cssEntry`, `tsconfig`) are relative to `PKG_DIR`, NOT repo root.

## Tailwind v4
`frontend/src/styles.css` uses `@import "tailwindcss"` — esbuild cannot process this.
Must use pre-compiled Vite output: run `buildCmd` to produce `frontend/.ds-styles.css`.

## DTS generation (noEmit: true)
`frontend/tsconfig.app.json` has `noEmit: true` — no `.d.ts` files exist by default.
Must run `tsc -p frontend/tsconfig.ds-emit.json` to generate declarations in `frontend/.ds-types/`.
Then `frontend/index.d.ts` barrel re-exports all of them.

## Path aliases — CRITICAL ordering fix
In `tsconfig.ds-emit.json`, specific stub redirects MUST come BEFORE the `@/*` wildcard.
If `@/*` is first, TypeScript resolves `@/api/client` to the real source file instead of the stub,
causing it to follow the full import chain into `src/api/`, `openapi/`, etc., emitting
spurious `.d.ts` files outside `rootDir`.

Correct ordering:
  "@/api/client" → ".ds-type-stubs/api-client.d.ts"  (first)
  "@/ui/*"       → "./src/ui/*"                        (second)
  "@/*"          → "./src/*"                            (last — fallback only)

## QueryState excluded
`src/ui/QueryState.tsx` imports `@/api/client` and `@/app/layout/NotFoundPage` (app-level deps).
Excluded via `componentSrcMap: {"QueryState": null}` in config and from `tsconfig.ds-emit.json`.

## Components with thin floor cards (interaction-driven)
- Skeleton: blank by design (loading state)
- Tooltip: content only shows on hover — add text content with className prop in preview
- CopyableTextDisclosure, Disclosure, FormSection, PageShell: thin on static render

## ErrorCallout
Imports `type { ProblemDetails }` from `@/api/client` — only a type import.
Handled by stub. Keep in sync.

## Fonts — self-hosted Heebo
Claude Design runs sandboxed with no CDN access. Heebo is loaded via Google Fonts in
`frontend/index.html`, so it's absent from the Vite CSS output.

Fix applied: downloaded 3 subsets (hebrew, latin-ext, latin) to `ds-bundle/fonts/` and
created `ds-bundle/fonts/heebo.css` with `@font-face` ranges 300–800 pointing to local files.
`ds-bundle/styles.css` prepends `@import "./fonts/heebo.css"`.

**After a full rebuild** (`buildCmd` → re-copy `.ds-styles.css`), the styles.css in ds-bundle
is regenerated and the font import is lost. Re-add it manually before upload:
  `sed -i '' '1s/^/@import ".\/fonts\/heebo.css";\n/' ds-bundle/styles.css`
or automate by extending `buildCmd`.
