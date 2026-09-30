import { JOB_TEXT_MAX_BYTES } from "@/api/applications";

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

/* What a posting's source address is sent as: the trimmed address, or null for none. The
   posting's text is never trimmed - it is evidence - but a URL's surrounding whitespace
   carries nothing. */
export const normalizedSourceUrl = (value: string): string | null => {
  const trimmed = value.trim();
  return trimmed === "" ? null : trimmed;
};

/* The server stores a posting's text as one snapshot and refuses it past this many UTF-8
   bytes. Both forms that send a posting - intake and a new snapshot from Job Detail -
   check it before sending, so neither discovers the limit by a round trip. */
export const jobTextByteLength = (jobText: string): number => new TextEncoder().encode(jobText).length;

export const isJobTextWithinBudget = (jobText: string): boolean => jobTextByteLength(jobText) <= JOB_TEXT_MAX_BYTES;

export const JOB_TEXT_REQUIRED_MESSAGE = "יש להזין את טקסט המשרה.";
