import type { Emphasis, Language, ProfileName, Track } from "./contracts";

/* Which classification values this build recognizes, as runtime sets.

   The analysis document travels as an opaque object on the wire, so every classification
   field on it arrives as `unknown` and has to be narrowed at the read. That narrowing is
   the transport boundary's job, which is why the sets live here: reading a response is
   not a presentation concern, and `api/` reaching into a feature to ask which values
   exist was the layering inverted.

   Each set is a `Record` over the generated union, so a value added to the backend fails
   this build until it is registered - the same guarantee the Hebrew label maps in
   `features/preparation` carry over the same unions. Two exhaustive maps, both checked by
   the compiler, is not a list maintained twice: neither can quietly fall behind the
   schema, because neither compiles when it does. */

const tracks: Record<Track, true> = {
  development: true,
  sales: true,
  "tech-sales": true,
};

const profiles: Record<ProfileName, true> = {
  development: true,
  "field-sales": true,
  "account-manager": true,
  "key-account-manager": true,
  "sdr-bdr": true,
  "account-executive": true,
  "business-development": true,
  "sales-management": true,
  "tech-sales": true,
  "pre-sales-solutions-consultant": true,
};

const emphases: Record<Emphasis, true> = {
  "development-balanced": true,
  "development-backend": true,
  "development-ai": true,
  "new-business": true,
  "account-growth": true,
  leadership: true,
  "tech-consultative-sales": true,
  "balanced-sales": true,
};

const languages: Record<Language, true> = {
  en: true,
  he: true,
};

/* Fit has no generated union: it lives inside the analysis document rather than in the
   schema, so it is declared where the document is read and checked by membership at that
   read - which is what makes an unrecognized value arrive as absent rather than as
   `undefined` on a screen. */
export type FitLevel = "high" | "medium" | "low" | "unknown";

const fitLevels: Record<FitLevel, true> = {
  high: true,
  medium: true,
  low: true,
  unknown: true,
};

const memberOf =
  <T extends string>(members: Record<T, true>) =>
  (value: unknown): value is T =>
    typeof value === "string" && Object.hasOwn(members, value);

export const isTrack = memberOf<Track>(tracks);
export const isProfileName = memberOf<ProfileName>(profiles);
export const isEmphasis = memberOf<Emphasis>(emphases);
export const isLanguage = memberOf<Language>(languages);
export const isFitLevel = memberOf<FitLevel>(fitLevels);
