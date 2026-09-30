import { formatDateTime } from "@/utils/formatDateTime";

/* A stored timestamp inside a sentence. The formatted date and time are digits and
   separators, which a Hebrew line would otherwise reorder around the comma between them,
   so the value is its own left-to-right island; the machine-readable instant rides on
   `<time>`. An unparseable value is shown exactly as stored (`formatDateTime`). */
export const DateTime = ({ format, value }: { format?: Parameters<typeof formatDateTime>[1]; value: string }) => (
  <bdi dir="ltr">
    <time dateTime={value}>{formatDateTime(value, format)}</time>
  </bdi>
);
