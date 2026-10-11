import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { apiRequest, onSessionLost } from "@/api/client";
import { json } from "@/test/fixtures";
import { ChangePasswordForm, SessionGate, SignOutButton, safeNextPath } from ".";
import { LoginPage } from "./pages/LoginPage";

const me = { id: "user-1", email: "candidate@example.com", created_at: "2026-10-11T12:00:00+00:00" };
const unauthenticated = (code = "AUTHENTICATION_REQUIRED") =>
  json({ type: "about:blank", title: "Unauthorized", status: 401, code, detail: "no" }, 401, {
    "Content-Type": "application/problem+json",
  });

const Where = () => {
  const location = useLocation();
  return <p data-testid="where">{`${location.pathname}${location.search}`}</p>;
};

const renderApp = (entry: string) => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const view = render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[entry]}>
        <Routes>
          <Route element={<LoginPage />} path="/login" />
          <Route
            element={
              <SessionGate>
                <p>מסך פנימי</p>
                <SignOutButton />
              </SessionGate>
            }
            path="*"
          />
        </Routes>
        <Where />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return { ...view, client };
};

afterEach(() => {
  vi.unstubAllGlobals();
  onSessionLost(() => undefined);
  localStorage.clear();
  sessionStorage.clear();
});

describe("sign-in", () => {
  it("sends a signed-out reader to sign-in and back to where they were", async () => {
    let signedIn = false;
    const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/v1/auth/me") return Promise.resolve(signedIn ? json(me) : unauthenticated());
      if (url === "/api/v1/auth/login") {
        signedIn = true;
        expect(JSON.parse(String(init?.body))).toEqual({ email: "candidate@example.com", password: "a long password" });
        return Promise.resolve(json(me));
      }
      throw new Error(`unexpected ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    renderApp("/applications/a-1?tab=cv");

    await waitFor(() =>
      expect(screen.getByTestId("where")).toHaveTextContent(
        `/login?next=${encodeURIComponent("/applications/a-1?tab=cv")}`,
      ),
    );
    fireEvent.change(screen.getByLabelText("אימייל"), { target: { value: "candidate@example.com" } });
    fireEvent.change(screen.getByLabelText("סיסמה"), { target: { value: "a long password" } });
    fireEvent.click(screen.getByRole("button", { name: "התחברות" }));

    expect(await screen.findByText("מסך פנימי")).toBeInTheDocument();
    expect(screen.getByTestId("where")).toHaveTextContent("/applications/a-1?tab=cv");
  });

  it("says the same thing for any failed sign-in and stays on the screen", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(unauthenticated("INVALID_CREDENTIALS"))),
    );
    renderApp("/login");

    fireEvent.change(screen.getByLabelText("אימייל"), { target: { value: "x@example.com" } });
    fireEvent.change(screen.getByLabelText("סיסמה"), { target: { value: "wrong" } });
    fireEvent.click(screen.getByRole("button", { name: "התחברות" }));

    expect(await screen.findByText("ההתחברות נכשלה")).toBeInTheDocument();
    expect(screen.getByText(/האימייל או הסיסמה שגויים/)).toBeInTheDocument();
    expect(screen.getByTestId("where")).toHaveTextContent("/login");
  });

  it("returns only to a path inside the app", () => {
    expect(safeNextPath("/applications/a-1")).toBe("/applications/a-1");
    for (const refused of [null, "https://evil.example", "//evil.example", "/login?next=/x", "applications"]) {
      expect(safeNextPath(refused)).toBe("/");
    }
  });
});

describe("signing out", () => {
  it("ends the session, clears the reader's browser state, and returns to sign-in", async () => {
    const fetchMock = vi.fn((input: string | URL | Request) => {
      const url = String(input);
      if (url === "/api/v1/auth/me") return Promise.resolve(json(me));
      if (url === "/api/v1/auth/logout") return Promise.resolve(new Response(null, { status: 204 }));
      throw new Error(`unexpected ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    localStorage.setItem("intake-draft", "job text");
    sessionStorage.setItem("board-return", "/");

    const { client } = renderApp("/");
    fireEvent.click(await screen.findByRole("button", { name: "התנתקות" }));

    await waitFor(() => expect(screen.getByTestId("where")).toHaveTextContent("/login"));
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/auth/logout", expect.objectContaining({ method: "POST" }));
    expect(localStorage.length).toBe(0);
    expect(sessionStorage.length).toBe(0);
    expect(client.getQueryCache().getAll()).toEqual([]);
  });
});

describe("a session lost under an open screen", () => {
  it("is reported once by the client, for AUTHENTICATION_REQUIRED only", async () => {
    const lost = vi.fn();
    onSessionLost(lost);
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(unauthenticated())),
    );
    await expect(apiRequest("/api/v1/settings")).rejects.toThrow("no");
    expect(lost).toHaveBeenCalledTimes(1);

    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(unauthenticated("INVALID_CREDENTIALS"))),
    );
    await expect(apiRequest("/api/v1/auth/login", { method: "POST", body: {} })).rejects.toThrow("no");
    expect(lost).toHaveBeenCalledTimes(1);
  });
});

describe("changing the password", () => {
  it("sends the current and new password and reports the other sessions ended", async () => {
    const fetchMock = vi.fn((_input: string | URL | Request, _init?: RequestInit) =>
      Promise.resolve(new Response(null, { status: 204 })),
    );
    vi.stubGlobal("fetch", fetchMock);
    render(
      <QueryClientProvider client={new QueryClient()}>
        <ChangePasswordForm />
      </QueryClientProvider>,
    );

    fireEvent.change(screen.getByLabelText("סיסמה נוכחית"), { target: { value: "old password here" } });
    fireEvent.change(screen.getByLabelText("סיסמה חדשה"), { target: { value: "new password here" } });
    fireEvent.click(screen.getByRole("button", { name: "שינוי סיסמה" }));

    expect(await screen.findByText("כל ההתחברויות האחרות הסתיימו.")).toBeInTheDocument();
    const [url, init] = fetchMock.mock.calls[0] ?? [];
    expect(url).toBe("/api/v1/auth/change-password");
    expect(JSON.parse(String(init?.body))).toEqual({
      current_password: "old password here",
      new_password: "new password here",
    });
  });
});
