import React from "react";
import ReactDOM from "react-dom/client";
import CoworkStandalone from "./CoworkStandalone";
import "../styles/index.css";
import { registerDefaultEelBridge } from "./lib/eel";

registerDefaultEelBridge();

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <CoworkStandalone />
  </React.StrictMode>,
);
