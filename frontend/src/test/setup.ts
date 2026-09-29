import { format } from "node:util";

import { cleanup, configure } from "@testing-library/react";
import { afterEach } from "vitest";

import "@testing-library/jest-dom/vitest";

/* `reportError` writes a failure's code, status and detail to the console on purpose -
   that is where the page sends what it does not show. The tests that drive failure paths
   therefore print one diagnostic per refusal, and a green run read as a wall of stderr
   that hid the lines worth reading. Its output is recognised by shape, not by a list of
   scopes: a snake_case scope followed by one context object, which is how every call
   site and `AppErrorBoundary` write it. Anything else - a React warning, an act()
   warning - still reaches stderr.

   JSDOM_GAPS is the deliberate exception list: a warning caused by jsdom lacking
   something a browser has, never by the component. */
const JSDOM_GAPS: { pattern: RegExp; reason: string }[] = [
  { pattern: /The tag <search> is unrecognized/, reason: "jsdom has no HTMLSearchElement; browsers do" },
];

const isDiagnostic = (args: unknown[]): boolean =>
  args.length === 2 && typeof args[0] === "string" && /^[a-z]+(_[a-z]+)+$/.test(args[0]) && typeof args[1] === "object";

/* React logs a printf-style template ("The tag <%s> ..." plus its arguments), so the
   pattern is matched against the formatted line, which is what stderr would show. */
const isJsdomGap = (args: unknown[]): boolean => {
  const line = format(...args);
  return JSDOM_GAPS.some(({ pattern }) => pattern.test(line));
};

for (const level of ["warn", "error"] as const) {
  const write = console[level].bind(console);
  console[level] = (...args: unknown[]) => {
    if (!isDiagnostic(args) && !isJsdomGap(args)) {
      write(...args);
    }
  };
}

/* Testing Library only auto-cleans when Vitest globals are on. They are off here, so
   the teardown is explicit rather than absent. */
afterEach(cleanup);

/* The other half of the starvation `fileParallelism: false` addresses in the Vitest
   config. Serial file scheduling stopped whole jsdom environments from competing, but
   each file still builds one and tears it down - across the suite that is most of the
   wall clock - and a `findBy*` inside a slow file could still exhaust Testing Library's
   one-second default while its render was perfectly correct.

   The symptom was a suite that failed two to four tests per full run, never the same
   ones, every one of them passing when its file was run alone. That is a clock running
   out, not a component misbehaving, so the clock is what is adjusted. Nothing here
   weakens an assertion: a query that will never be satisfied still fails, and only takes
   longer to say so. */
configure({ asyncUtilTimeout: 5_000 });

/* jsdom implements <dialog> as an element but not its modal methods, so a component that
   calls `showModal` throws where a browser would open the dialog. The shim is the
   smallest thing that makes the element behave as the DOM specifies for these tests: the
   `open` attribute reflects the state, and closing fires the `close` event that React
   components listen for. It lives here rather than in one test file because every dialog
   in this app is opened the same way. */
if (typeof HTMLDialogElement !== "undefined") {
  const open = (dialog: HTMLDialogElement) => {
    dialog.open = true;
  };

  HTMLDialogElement.prototype.showModal ??= function showModal(this: HTMLDialogElement) {
    open(this);
  };
  HTMLDialogElement.prototype.show ??= function show(this: HTMLDialogElement) {
    open(this);
  };
  HTMLDialogElement.prototype.close ??= function close(this: HTMLDialogElement) {
    this.open = false;
    this.dispatchEvent(new Event("close"));
  };
}
