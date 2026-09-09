/* The Applications feature's public surface: one Application as a record - which job it
   is, where it stands on both axes, and the way into the domains that do the work.

   It composes preparation, recruitment and its own artifact inventory; it owns none of
   their logic. What it does own is the Application's identity, so the breadcrumb trail
   and the posting's source line are exported for the screens that name the same record
   from outside. */
export { ApplicationPage } from "./pages/ApplicationPage";
/* One hierarchy for every view of an Application, so the editor and the revision screen
   cannot describe the same parent differently. */
export { ApplicationBreadcrumbs } from "./components/ApplicationBreadcrumbs";
export { applicationLabel, sourceHostname } from "./model/applicationPresentation";
export { LABEL_MAX_CHARACTERS, SOURCE_URL_MAX_CHARACTERS } from "./model/applicationInput";
