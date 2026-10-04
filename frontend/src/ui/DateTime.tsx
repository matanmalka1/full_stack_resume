import { formatDateTime } from "@/utils/formatDateTime";

type DateTimeStyle = NonNullable<Parameters<typeof formatDateTime>[1]>;

/* A stored timestamp inside a sentence, isolated so the line around it cannot reorder it;
   the machine-readable instant rides on `<time>`. The numeric styles are digits and
   separators, which a Hebrew line would reorder around the comma between them, so they are
   a left-to-right island. `medium` carries the Hebrew month name ("30 בספט׳ 2026, 22:33"):
   forced left-to-right, the month and the numbers swapped places, so it keeps the Hebrew
   direction it was formatted in. An unparseable value is shown exactly as stored
   (`formatDateTime`). */
export const DateTime = ({ format = "medium", value }: { format?: DateTimeStyle; value: string }) => (
  <bdi dir={format === "medium" ? "rtl" : "ltr"}>
    <time dateTime={value}>{formatDateTime(value, format)}</time>
  </bdi>
);
