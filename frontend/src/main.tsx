import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { AppErrorBoundary } from "./app/AppErrorBoundary";
import { AppProviders } from "./app/AppProviders";
import "./styles.css";

const root = document.getElementById("root");

if (root === null) {
  throw new Error("Frontend root element is missing");
}

createRoot(root).render(
  <StrictMode>
    <AppErrorBoundary>
      <AppProviders />
    </AppErrorBoundary>
  </StrictMode>,
);
