import { useEffect, useState } from "react";

/* A value that settles before anything acts on it.

   The search field is what needs this: every keystroke is a question for the server, and
   without it typing a company name sent one request per character and raced their answers
   against each other. The control stays fully responsive - what is delayed is the request,
   not the typing.

   The delay is restarted by each change and cleared on unmount, so a value that never
   settles never fires. */
export const useDebouncedValue = <T>(value: T, delayMs: number): T => {
  const [settled, setSettled] = useState(value);

  useEffect(() => {
    /* A value that has already settled must not wait again: without this, clearing the
       field or arriving from a shared link would blank the board for the delay before
       showing the same rows it was already holding. */
    if (Object.is(value, settled)) {
      return;
    }

    const timer = setTimeout(() => setSettled(value), delayMs);
    return () => clearTimeout(timer);
  }, [delayMs, settled, value]);

  return settled;
};
