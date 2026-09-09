/* How one Application is named wherever it is named as a single line: the company, an
   em dash, the target role. It lives here because four surfaces said it in three
   different ways - an en dash in the breadcrumb trail, an em dash in the intake and close
   dialogs, a middle dot on the revision screen - three separators for one relationship.

   The fallback is the same one the breadcrumb trail carried: a record whose canonical
   values have not loaded is named generically rather than by its id. */
export const applicationLabel = (company?: string | null, targetRole?: string | null): string =>
  company == null || company === "" || targetRole == null || targetRole === ""
    ? "פרטי משרה"
    : `${company} — ${targetRole}`;

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
