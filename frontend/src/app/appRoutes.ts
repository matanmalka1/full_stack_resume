const segment = (value: string): string => encodeURIComponent(value);
const application = (applicationId: string): string => `/applications/${segment(applicationId)}`;

export const appRoutes = {
  home: "/",
  newApplication: "/applications/new",
  settings: "/settings",
  application,
  preparation: (applicationId: string): string => `${application(applicationId)}/preparation`,
  draft: (applicationId: string): string => `${application(applicationId)}/draft`,
  revision: (revisionId: string): string => `/revisions/${segment(revisionId)}`,
} as const;
