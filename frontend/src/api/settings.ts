import { queryOptions } from "@tanstack/react-query";

import { apiRequest } from "./client";
import type { Settings, UpdateSettingsRequest } from "./contracts";

export interface SettingsRead {
  settings: Settings;
  etag: string | null;
}

export const settingsQueryKey = ["settings"] as const;

export const readSettings = async (signal?: AbortSignal): Promise<SettingsRead> => {
  const response = await apiRequest<Settings>("/api/v1/settings", { signal });
  return { settings: response.data, etag: response.etag };
};

export const settingsQueryOptions = queryOptions({
  queryKey: settingsQueryKey,
  queryFn: ({ signal }) => readSettings(signal),
});

export const updateSettings = async (body: UpdateSettingsRequest, etag: string): Promise<SettingsRead> => {
  const response = await apiRequest<Settings>("/api/v1/settings", {
    method: "PATCH",
    body,
    etag,
  });
  return { settings: response.data, etag: response.etag };
};

/* Which lane a command that has both of them runs in when the screen did not ask the
   reader to choose one. All three answers have to agree: a provider configured, AI
   enabled, and the Settings default naming the AI lane. Enabling AI is permission, not
   the choice itself - a reader who left the default on deterministic asked for the
   deterministic lane, and this used to hand them the paid one anyway.

   `undefined` omits `provider` from the request, which is the deterministic lane.

   Analysis does not read this. It is AI-only with no deterministic form to default to,
   so it reads `aiRegenerationAvailable` and is simply unavailable without a provider. */
export const executionProvider = (settings: Settings | undefined): "openai" | undefined =>
  settings?.provider_configured && settings.ai_enabled && settings.default_execution_mode === "ai"
    ? "openai"
    : undefined;

export const aiRegenerationAvailable = (settings: Settings | undefined): boolean =>
  settings?.provider_configured === true && settings.ai_enabled === true;
