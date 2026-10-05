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

/* Analysis, drafting and regeneration are AI-only and AI has no switch: without a
   configured provider none of them can run, and the screens offering them say so. */
const aiRegenerationAvailable = (settings: Settings | undefined): boolean =>
  settings?.provider_configured === true;

/* Whether an AI command can run, with "settings not read yet" kept apart from "no usable
   provider". Screens decide for themselves what to do while it is "loading" - some hold
   the control, some assume the common case - but none re-derives the three states. */
export type AiAvailability = "loading" | "available" | "missing";

export const aiAvailability = (settings: Settings | undefined): AiAvailability =>
  settings === undefined ? "loading" : aiRegenerationAvailable(settings) ? "available" : "missing";
