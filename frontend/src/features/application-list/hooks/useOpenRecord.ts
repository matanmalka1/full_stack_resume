import type { KeyboardEvent, MouseEvent } from "react";
import { useNavigate } from "react-router-dom";

/* A board record - a table row, a card, a stage card - opens as a whole but yields to
   real controls and to text selection. Its own anchor stays the native keyboard and
   screen-reader route into it; this only makes the rest of its surface a target. */
export const useOpenRecord = (href: string) => {
  const navigate = useNavigate();

  const onClick = (event: MouseEvent<HTMLElement>) => {
    if (event.defaultPrevented || event.target instanceof Element === false) {
      return;
    }

    /* The record looks and behaves like a link, so it yields to the gestures that open
       a link somewhere else. Without this, Cmd- or Ctrl-clicking the body navigated in
       place - the one thing the reader was asking it not to do - while the same gesture
       on the anchor inside it opened a tab. */
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

    navigate(href);
  };

  const onKeyDown = (event: KeyboardEvent<HTMLElement>) => {
    if ((event.key === "Enter" || event.key === " ") && event.target === event.currentTarget) {
      event.preventDefault();
      navigate(href);
    }
  };

  return { onClick, onKeyDown };
};
