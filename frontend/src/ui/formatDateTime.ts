type DateTimeStyle = "medium" | "short";

const formatters: Record<DateTimeStyle, Intl.DateTimeFormat> = {
  medium: new Intl.DateTimeFormat("he-IL", { dateStyle: "medium", timeStyle: "short" }),
  short: new Intl.DateTimeFormat("he-IL", { dateStyle: "short", timeStyle: "short" }),
};

/* Stored timestamps are evidence. If a legacy or external value cannot be parsed, keep
   the exact value visible rather than replacing it with an invented date or “Invalid”. */
export const formatDateTime = (value: string, style: DateTimeStyle = "medium"): string => {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : formatters[style].format(parsed);
};

export const dateTimesMatch = (left: string, right: string): boolean => {
  const leftTime = new Date(left).getTime();
  const rightTime = new Date(right).getTime();

  return Number.isNaN(leftTime) || Number.isNaN(rightTime) ? left === right : leftTime === rightTime;
};
