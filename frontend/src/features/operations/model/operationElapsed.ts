/* A stretch of time in the words the report uses: seconds under a minute, then minutes and
   seconds. Null when the two ends do not make a stretch - a missing or reversed clock. */
export const durationLabel = (start: string, end: string | number): string | null => {
  const milliseconds = (typeof end === "number" ? end : Date.parse(end)) - Date.parse(start);
  if (!Number.isFinite(milliseconds) || milliseconds < 0) return null;
  const seconds = Math.floor(milliseconds / 1000);
  return seconds < 60 ? `${seconds} שניות` : `${Math.floor(seconds / 60)} דקות ו־${seconds % 60} שניות`;
};
