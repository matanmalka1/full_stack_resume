import { describe, expect, it } from "vitest";

import type { Settings } from "./contracts";
import { aiRegenerationAvailable, executionProvider } from "./settings";

const settings = (overrides: Partial<Settings> = {}): Settings => ({
  edit_version: 0, auto_generate_when_review_not_required: false, ai_enabled: true,
  ai_enabled_override: null, default_execution_mode: "deterministic", open_browser_on_launch: true,
  provider_configured: true, ui_density: "comfortable", ui_text_size: "normal", ...overrides,
});

describe("effective Settings behavior", () => {
  it("omits provider in deterministic mode", () => {
    expect(executionProvider(settings())).toBeUndefined();
  });

  it("names OpenAI in manual AI mode", () => {
    expect(executionProvider(settings({ default_execution_mode: "ai" }))).toBe("openai");
  });

  it("falls back to deterministic execution when AI is disabled or unconfigured", () => {
    expect(executionProvider(settings({ default_execution_mode: "ai", ai_enabled: false }))).toBeUndefined();
    expect(executionProvider(settings({ default_execution_mode: "ai", provider_configured: false }))).toBeUndefined();
  });

  it("requires both provider configuration and effective AI enablement for regeneration", () => {
    expect(aiRegenerationAvailable(settings())).toBe(true);
    expect(aiRegenerationAvailable(settings({ provider_configured: false }))).toBe(false);
  });

  it("does not treat missing Settings as permission to run AI", () => {
    expect(aiRegenerationAvailable(undefined)).toBe(false);
  });
});
