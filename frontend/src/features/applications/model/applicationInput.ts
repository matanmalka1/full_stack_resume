/* Native input affordances, not a second validation policy: they stop the user typing
   past limits the server would refuse anyway. The refusal itself stays the server's. */
export const LABEL_MAX_CHARACTERS = 500;
export const SOURCE_URL_MAX_CHARACTERS = 2048;

/* Mirrors the server's `_SOURCE_URL` fullmatch (`^https?://\S+$`, case-insensitive).
   Catching the common typo here saves the round trip; the server stays authoritative,
   since this form never widens what it accepts. */
const SOURCE_URL_PATTERN = /^https?:\/\/\S+$/i;

/* The field is optional, so an empty value is never an error here - only a non-empty
   value that does not look like a URL is. */
export const validateSourceUrl = (value: string): true | string => {
  const trimmed = value.trim();
  return trimmed === "" || SOURCE_URL_PATTERN.test(trimmed) || "הכתובת חייבת להתחיל ב-http:// או https:// וללא רווחים.";
};
