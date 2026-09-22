type DateTimeStyle = "date" | "medium" | "short";

const formatters: Record<DateTimeStyle, Intl.DateTimeFormat> = {
  date: new Intl.DateTimeFormat("he-IL", { dateStyle: "short" }),
  medium: new Intl.DateTimeFormat("he-IL", { dateStyle: "medium", timeStyle: "short" }),
  short: new Intl.DateTimeFormat("he-IL", { dateStyle: "short", timeStyle: "short" }),
};

const dateFormatter = new Intl.DateTimeFormat("he-IL", { dateStyle: "medium", timeZone: "UTC" });

/* Stored timestamps are evidence. If a value cannot be parsed, keep the exact value
   visible rather than replacing it with an invented date or “Invalid”. */
export const formatDateTime = (value: string, style: DateTimeStyle = "medium"): string => {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : formatters[style].format(parsed);
};

/* A calendar date has no time zone. Parse it at UTC midnight and format it in UTC so
   west-of-UTC clients cannot move the stored day backwards while presenting it. */
export const formatDate = (value: string): string => {
  const parsed = new Date(`${value}T00:00:00Z`);
  return Number.isNaN(parsed.getTime()) ? value : dateFormatter.format(parsed);
};
