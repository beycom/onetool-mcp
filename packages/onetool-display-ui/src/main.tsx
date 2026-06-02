import { createRoot } from "react-dom/client";
import { App } from "./App";
import "./styles/app.css";

const root = document.getElementById("onetool-display-root");
if (!root) {
  throw new Error("Missing OneTool display root element.");
}

createRoot(root).render(<App />);
