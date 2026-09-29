/* Asks the browser to confirm leaving the page. `preventDefault` is the standard signal;
   `returnValue` is the older one, and Chrome before 119 and some embedded webviews show
   the prompt only when it is set. The string itself is never displayed. */
export const confirmUnload = (event: BeforeUnloadEvent): void => {
  event.preventDefault();
  event.returnValue = "";
};
