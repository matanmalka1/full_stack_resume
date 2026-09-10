/* The facts feature's public surface: exactly what the draft editor and the settings
   screen reach the knowledge store through, and nothing deeper. A consumer that needs
   something not listed here needs it added here, not imported from inside. */
export { useCaptureClaimFact } from "./api/mutations";
export { useFactDetail } from "./api/queries";
export { FactEventHistory } from "./components/FactEventHistory";
export { FactsPage } from "./pages/FactsPage";
export { FactCoreFields, FactProvenanceField, FactSourceField, FactTagsField } from "./components/FactFormFieldset";
export { emptyFactForm, parseFactTags, replacementFactForm, type FactFormFields } from "./model/factForm";
export { factLabelInLanguage, factStatusLabel } from "./model/factLabels";
