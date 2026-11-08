import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./styles/tokens.css";
import "./styles/base.css";
import "./styles/components.css";
import "./styles/pages.css";
import "./styles/responsive.css";
import "./styles/capture.css";

const root = document.getElementById("root");
if (!root) throw new Error("The application root is missing");
createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
