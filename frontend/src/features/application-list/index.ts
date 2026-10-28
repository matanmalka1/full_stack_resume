/* For a caller outside the board that names an Application the same way - the shell's
   global search. */
export { ApplicationSummary } from "./components/ApplicationSummary";

/* For the Application's own screen, which offers the board's record commands - the
   menu, its close and delete confirmations, the details dialog - over the same mutations,
   so the two places cannot drift apart in what a command does. */
export { ApplicationRecordActions } from "./components/ApplicationListItemActions";
export { ApplicationDetailsDialog } from "./components/ApplicationDetailsDialog";
export { CloseApplicationDialog } from "./components/CloseApplicationDialog";
export { DeleteApplicationDialog } from "./components/DeleteApplicationDialog";
export { useApplicationListMutations } from "./api/mutations";
