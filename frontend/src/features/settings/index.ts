/* The settings feature's public surface: names of setting values that other screens
   report, the live settings read every screen shares, and the display preview the app
   shell applies while the form is open. The screen itself is reached through the router. */
export {
  type DisplaySettings,
  DisplaySettingsPreviewProvider,
  useDisplaySettingsPreview,
} from "./components/DisplaySettingsPreview";
export { useAiAvailability, useSettings } from "./hooks/useSettings";
export { reasoningEffortLabels } from "./settings.model";
