import { queryOptions } from "@tanstack/react-query";

import { apiRequest } from "./client";
import type { Settings, UpdateSettingsRequest } from "./contracts";

export interface SettingsRead {
  settings: Settings;
  etag: string | null;
}

export const settingsQueryKey = ["settings"] as const;

export const settingsQueryOptions = queryOptions({
  queryKey: settingsQueryKey,
  queryFn: async ({ signal }): Promise<SettingsRead> => {
    const response = await apiRequest<Settings>("/api/v1/settings", { signal });
    return { settings: response.data, etag: response.etag };
  },
});

export const updateSettings = async (
  body: UpdateSettingsRequest,
  etag: string,
): Promise<SettingsRead> => {
  const response = await apiRequest<Settings>("/api/v1/settings", {
    method: "PATCH",
    body,
    etag,
  });
  return { settings: response.data, etag: response.etag };
};

export const executionProvider = (settings: Settings | undefined): "openai" | undefined =>
  settings?.default_execution_mode === "ai" &&
  settings.provider_configured &&
  settings.ai_enabled
    ? "openai"
    : undefined;

export const aiRegenerationAvailable = (settings: Settings | undefined): boolean =>
  settings?.provider_configured === true && settings.ai_enabled === true;
