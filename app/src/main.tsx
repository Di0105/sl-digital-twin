import React from "react";
import ReactDOM from "react-dom/client";
import "cesium/Build/Cesium/Widgets/widgets.css";
import "./styles.css";
import App from "./AppRoot";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
