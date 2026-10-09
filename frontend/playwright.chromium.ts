import { existsSync } from "node:fs";
import { join } from "node:path";

import { devices } from "@playwright/test";

/* The one Chromium project both configurations run.

   Playwright looks for the browser build its own version pins. A cloud agent container
   (`CLAUDE_CODE_REMOTE=true`) ships a preinstalled Chromium under
   `$PLAYWRIGHT_BROWSERS_PATH/chromium` instead and may not hold that build, so there the
   suite launches the preinstalled one. `CV_PLAYWRIGHT_CHROMIUM` names an executable
   explicitly anywhere. Elsewhere - a workstation, GitHub CI - nothing changes: the
   browser `npx playwright install chromium` placed is used. */
const executablePath = (): string | undefined => {
  const explicit = process.env.CV_PLAYWRIGHT_CHROMIUM;
  if (explicit) return explicit;
  const browsers = process.env.PLAYWRIGHT_BROWSERS_PATH;
  if (process.env.CLAUDE_CODE_REMOTE !== "true" || !browsers) return undefined;
  const preinstalled = join(browsers, "chromium");
  return existsSync(preinstalled) ? preinstalled : undefined;
};

const chromiumPath = executablePath();

export const chromiumProject = {
  name: "chromium",
  use: {
    ...devices["Desktop Chrome"],
    ...(chromiumPath === undefined ? {} : { launchOptions: { executablePath: chromiumPath } }),
  },
};
