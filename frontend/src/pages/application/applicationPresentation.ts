/* The posting's origin as the host alone, without `www.`. A URL the browser cannot
   parse is not guessed at; each presentation can provide the fallback appropriate to
   its available source data. */
export const sourceHostname = (url: string | null | undefined): string | null => {
  if (url == null || url === "") {
    return null;
  }

  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return null;
  }
};
