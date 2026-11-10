/* The Applications feature's public surface: one Application as a record - which job it
   is, where its CV stands, and the way into the domains that do the work.

   It composes preparation and its own artifact inventory; it owns none of
   their logic. What it does own is the Application's identity, so the label is exported
   for the screens that name the same record from outside. Its screens are not exported: the route table loads each one on its own. */
export { applicationLabel } from "./model/applicationPresentation";
export {
  isJobTextWithinBudget,
  JOB_TEXT_REQUIRED_MESSAGE,
  jobTextByteLength,
  LABEL_MAX_CHARACTERS,
  normalizedSourceUrl,
  SOURCE_URL_MAX_CHARACTERS,
  validateSourceUrl,
} from "./model/applicationInput";
