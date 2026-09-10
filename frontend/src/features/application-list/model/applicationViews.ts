import { Kanban, LayoutGrid, Table2 } from "lucide-react";

/* How the same page of Applications is drawn. It is a reader's preference about
   presentation, not part of the query: switching it re-reads nothing and changes no
   URL, so it lives beside the board's other presentation decisions rather than in
   `applicationListParams`. */
export type ViewMode = "table" | "cards" | "pipeline";

export const viewModeOptions = [
  { icon: Table2, label: "טבלה", value: "table" },
  { icon: LayoutGrid, label: "כרטיסים", value: "cards" },
  { icon: Kanban, label: "שלבים", value: "pipeline" },
] as const;

const VIEW_MODE_STORAGE_KEY = "cv:application-list:view-mode";
const isViewMode = (value: string | null): value is ViewMode =>
  value === "table" || value === "cards" || value === "pipeline";

/* A phone gets cards, because the table's stacked fallback is taller than the card it
   would fall back to. Otherwise the last view the reader picked in this tab, so a
   record's own page doesn't spend it back to the default - not the URL, since it is
   still a presentation preference rather than part of the query. */
export const initialViewMode = (): ViewMode => {
  const stored = typeof window.sessionStorage === "object" ? window.sessionStorage.getItem(VIEW_MODE_STORAGE_KEY) : null;
  if (isViewMode(stored)) {
    return stored;
  }

  return typeof window.matchMedia === "function" && window.matchMedia("(max-width: 639px)").matches
    ? "cards"
    : "table";
};

export const rememberViewMode = (viewMode: ViewMode): void => {
  if (typeof window.sessionStorage === "object") {
    window.sessionStorage.setItem(VIEW_MODE_STORAGE_KEY, viewMode);
  }
};
