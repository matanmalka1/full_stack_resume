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

/* A phone gets cards, because the table's stacked fallback is taller than the card it
   would fall back to. Read once, at mount: a reader who then picks a view keeps it. */
export const initialViewMode = (): ViewMode =>
  typeof window.matchMedia === "function" && window.matchMedia("(max-width: 639px)").matches ? "cards" : "table";
