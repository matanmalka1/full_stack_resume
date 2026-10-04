import { createContext, type ReactNode, useCallback, useContext, useId, useRef } from "react";
import type { Settings } from "@/api/contracts";
export type DisplaySettings = Pick<Settings, "ui_density" | "ui_text_size" | "ui_theme">;
const DisplaySettingsPreviewContext = createContext<(owner: string, settings: DisplaySettings | null) => void>(
  () => undefined,
);
export const DisplaySettingsPreviewProvider = ({
  children,
  onPreview,
}: {
  children: ReactNode;
  onPreview: (settings: DisplaySettings | null) => void;
}) => {
  const previews = useRef(new Map<string, DisplaySettings>());
  const update = useCallback(
    (owner: string, settings: DisplaySettings | null) => {
      previews.current.delete(owner);
      if (settings !== null) previews.current.set(owner, settings);
      onPreview(Array.from(previews.current.values()).at(-1) ?? null);
    },
    [onPreview],
  );
  return <DisplaySettingsPreviewContext.Provider value={update}>{children}</DisplaySettingsPreviewContext.Provider>;
};
export const useDisplaySettingsPreview = () => {
  const update = useContext(DisplaySettingsPreviewContext);
  const owner = useId();
  return useCallback((settings: DisplaySettings | null) => update(owner, settings), [owner, update]);
};
