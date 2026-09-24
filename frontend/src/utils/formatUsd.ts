/* A dollar amount as the reader wants to see it: cents from one cent up, and two
   significant digits below that. A single AI call costs fractions of a cent, and the raw
   decimal string ("0.00002806") read as noise while "<$0.01" would hide how small it was.
   The backend's string is the source; an unparseable one is shown as it came. */
export const formatUsd = (value: string): string => {
  const amount = Number(value);
  if (value.trim() === "" || !Number.isFinite(amount)) return `$${value}`;
  if (amount === 0) return "$0";
  if (Math.abs(amount) >= 0.01) {
    return `$${amount.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  }
  return `$${Number(amount.toPrecision(2)).toLocaleString("en-US", { maximumSignificantDigits: 2 })}`;
};
