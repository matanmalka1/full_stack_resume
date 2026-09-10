import { cleanup, configure } from "@testing-library/react";
import { afterEach } from "vitest";

import "@testing-library/jest-dom/vitest";

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
