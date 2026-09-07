/* The facts feature's public surface: exactly what the draft editor and the settings
   screen reach the knowledge store through, and nothing deeper. A consumer that needs
   something not listed here needs it added here, not imported from inside. */
export { useCaptureClaimFact } from "./api/factMutations";
export { useFactDetail } from "./api/factQueries";
export { FactEventHistory } from "./components/FactEventHistory";
export { FactLifecyclePanel } from "./components/FactLifecyclePanel";
export { FactPoolBrowser } from "./components/FactPoolBrowser";
export { FactCoreFields, FactProvenanceField, FactSourceField, FactTagsField } from "./components/FactFormFieldset";
export { emptyFactForm, parseFactTags, type FactFormFields } from "./model/factForm";
export { factLabelInLanguage, factStatusLabel } from "./model/factLabels";
