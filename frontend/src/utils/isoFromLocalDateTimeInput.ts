/** Convert a datetime-local value without allowing an invalid date to reach toISOString. */
export const isoFromLocalDateTimeInput = (value: string): string | null => {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed.toISOString();
};
