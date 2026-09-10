import { createContext, type ReactNode, useContext } from "react";

import type { Settings } from "@/api/contracts";

export type DisplaySettings = Pick<Settings, "ui_density" | "ui_text_size">;

const DisplaySettingsPreviewContext = createContext<(settings: DisplaySettings | null) => void>(() => undefined);

export const DisplaySettingsPreviewProvider = ({
  children,
  onPreview,
}: {
  children: ReactNode;
  onPreview: (settings: DisplaySettings | null) => void;
}) => <DisplaySettingsPreviewContext.Provider value={onPreview}>{children}</DisplaySettingsPreviewContext.Provider>;

export const useDisplaySettingsPreview = () => useContext(DisplaySettingsPreviewContext);
