//import { StrictMode } from 'react'
import { createRoot } from "react-dom/client";
import "./index.css";
import App from "./App.jsx";
import App1 from "./App1.jsx";
// Bootstrap5 và Bootstrap Icons
import "bootstrap/dist/css/bootstrap.min.css";
import "bootstrap-icons/font/bootstrap-icons.css";
import "bootstrap/dist/js/bootstrap.bundle.min.js";

// Chọn App để dùng:
// App = Backend mới (có parking management, barrier logic)
// App1 = Backend2 đơn giản (chỉ detect text biển số)
const USE_APP1 = true; // ĐỔI THÀNH false để dùng App chính

createRoot(document.getElementById("root")).render(
  //<StrictMode>
  USE_APP1 ? <App1 /> : <App />
  //</StrictMode>,
);
