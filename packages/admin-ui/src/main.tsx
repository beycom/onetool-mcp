import { createRoot } from "react-dom/client";
import { App } from "./app/App";
import "./styles/app.css";

const root = document.getElementById("onetool-admin-root");
if (!root) {
  throw new Error("Missing OneTool admin root element.");
}

createRoot(root).render(<App />);
