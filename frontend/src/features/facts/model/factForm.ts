import type { FactSource, FactStyle } from "./factLabels";

/* The one shape both fact-writing forms bind to. The two call sites send different
   requests from it - a free-standing pending fact, and a fact captured from a draft
   claim - but a person fills in the same seven things either way, so the fields, their
   defaults and their validation rules live here rather than being restated per form. */
export interface FactFormFields {
  english: string;
  hebrew: string;
  meaning: string;
  provenance: string;
  source: FactSource;
  style: FactStyle;
  tags: string;
}

/* Which knowledge file a new fact lands in by default. Only the active Profile's own
   track is guessed; the person can still pick any source, and a fact that belongs
   nowhere in particular is filed by hand. */
export const defaultFactSource = (profile: string | null): FactSource =>
  profile === "development" ? "development.md" : "sales.md";

export const emptyFactForm = (profile: string | null, meaning = ""): FactFormFields => ({
  english: "",
  hebrew: "",
  meaning,
  provenance: "",
  source: defaultFactSource(profile),
  style: "bullet",
  tags: "",
});

export const parseFactTags = (value: string): string[] =>
  value
    .split(",")
    .map((tag) => tag.trim())
    .filter(Boolean);

/* Field-level rules that stop an obviously empty write before it leaves the browser.
   The server's own validation stays authoritative - these only spare the round trip and
   name the missing field where the person is looking. */
export const factFieldRules = {
  english: { validate: (value: string) => value.trim() !== "" || "יש להזין ניסוח באנגלית." },
  meaning: { validate: (value: string) => value.trim() !== "" || "יש להזין משמעות." },
  provenance: { validate: (value: string) => value.trim() !== "" || "יש להזין מקור ואימות." },
  tags: { validate: (value: string) => parseFactTags(value).length > 0 || "יש להזין תגית אחת לפחות." },
} as const;
