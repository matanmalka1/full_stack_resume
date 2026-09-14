import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { expect, it } from "vitest";
import { usePreparationContinuation } from "./usePreparationContinuation";

const Surface = ({ applicationId, label }: { applicationId: string; label: string }) => {
  const { intent, mark } = usePreparationContinuation(applicationId);
  const location = useLocation();
  return (
    <section aria-label={label}>
      <button onClick={() => mark({ applicationId, draftOperationId: `op-${label}` })}>Queue {label}</button>
      <pre data-testid={`state-${label}`}>{JSON.stringify({ intent, state: location.state })}</pre>
    </section>
  );
};

it.each(["app-1", "app-2"])("keeps tabs independent when the second displays %s", (secondApplicationId) => {
  render(
    <>
      <MemoryRouter
        initialEntries={[
          { pathname: "/applications/app-1", state: { createdApplication: { applicationId: "app-1" } } },
        ]}
      >
        <Surface applicationId="app-1" label="first" />
      </MemoryRouter>
      <MemoryRouter initialEntries={["/applications/app-1"]}>
        <Surface applicationId={secondApplicationId} label="second" />
      </MemoryRouter>
    </>,
  );
  fireEvent.click(screen.getByRole("button", { name: "Queue first" }));
  expect(screen.getByTestId("state-first").textContent).toContain("op-first");
  expect(screen.getByTestId("state-first").textContent).toContain("createdApplication");
  expect(screen.getByTestId("state-second").textContent).not.toContain("op-first");
  fireEvent.click(screen.getByRole("button", { name: "Queue second" }));
  expect(screen.getByTestId("state-first").textContent).not.toContain("op-second");
  expect(screen.getByTestId("state-second").textContent).toContain("op-second");
});
