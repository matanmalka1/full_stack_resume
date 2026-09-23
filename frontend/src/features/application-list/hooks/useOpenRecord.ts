import type { KeyboardEvent, MouseEvent } from "react";

/* A board record - a table row, a card, a stage card - opens as a whole but yields to
   real controls and to text selection. What opening does is the caller's: the board
   opens the record's details. Its own link icon stays the native route straight to the
   work, for the keyboard, screen readers and a new tab. */
export const useOpenRecord = (onOpen: () => void) => {
  const onClick = (event: MouseEvent<HTMLElement>) => {
    if (event.defaultPrevented || event.target instanceof Element === false) {
      return;
    }

    /* Modified clicks are the reader asking for a link somewhere else, which only the
       record's own anchor can give; the body leaves them alone rather than answer with
       something else in place. */
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button !== 0) {
      return;
    }

    /* A click inside an open menu, even between its items, belongs to the menu. */
    if (event.target.closest("a, button, input, label, [role=menu]") !== null) {
      return;
    }

    if ((window.getSelection()?.toString() ?? "") !== "") {
      return;
    }

    onOpen();
  };

  const onKeyDown = (event: KeyboardEvent<HTMLElement>) => {
    if ((event.key === "Enter" || event.key === " ") && event.target === event.currentTarget) {
      event.preventDefault();
      onOpen();
    }
  };

  return { onClick, onKeyDown };
};
