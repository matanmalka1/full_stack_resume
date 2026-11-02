/* The Applications feature's public surface: one Application as a record - which job it
   is, where it stands on both axes, and the way into the domains that do the work.

   It composes preparation, recruitment and its own artifact inventory; it owns none of
   their logic. What it does own is the Application's identity, so the label is exported
   for the screens that name the same record from outside. Its screens are not exported: the route table loads each one on its own. */
export { applicationLabel } from "./model/applicationPresentation";
/* The record's quick look, which the board opens over its cards exactly as the hub
   opens it over its own record. */
export { ApplicationDetailsSheet } from "./components/ApplicationDetailsSheet";
export {
  isJobTextWithinBudget,
  JOB_TEXT_REQUIRED_MESSAGE,
  jobTextByteLength,
  LABEL_MAX_CHARACTERS,
  normalizedSourceUrl,
  SOURCE_URL_MAX_CHARACTERS,
  validateSourceUrl,
} from "./model/applicationInput";
