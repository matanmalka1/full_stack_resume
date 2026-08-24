import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

import "@testing-library/jest-dom/vitest";

/* Testing Library only auto-cleans when Vitest globals are on. They are off here, so
   the teardown is explicit rather than absent. */
afterEach(cleanup);
