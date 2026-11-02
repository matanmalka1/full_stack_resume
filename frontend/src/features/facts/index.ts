/* The facts feature's public surface: exactly what the draft editor reaches the
   knowledge store through, and nothing deeper. A consumer that needs something not
   listed here needs it added here, not imported from inside. */
export { useCaptureClaimFact } from "./api/mutations";
export { useFactDetail } from "./api/queries";
export { FactEventHistory } from "./components/FactEventHistory";
/* The one way a fact is written by hand, so a gap named elsewhere (a job requirement with
   no supporting fact) opens the same form, with the same pending result, as the pool. */
export { FactCreationDialog } from "./components/FactCreationDialog";
export {
  FactCoreFields,
  FactHebrewRenderingField,
  FactProvenanceField,
  FactSourceField,
  FactTagsField,
} from "./components/FactFormFieldset";
export { emptyFactForm, parseFactTags, type FactFormFields } from "./model/factForm";
export { factSearchText } from "./model/factFilters";
export { factLabel, factLabelInLanguage, factSourceLabel, factStatusLabel } from "./model/factLabels";
