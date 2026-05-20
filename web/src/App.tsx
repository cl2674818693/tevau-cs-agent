import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { BuLoginRoute } from "./routes/BuLoginRoute";
import { ChatRoute } from "./routes/ChatRoute";
import "./styles/globals.css";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<ChatRoute />} />
        <Route path="/bu/login" element={<BuLoginRoute />} />
        {/* /staff/* 路由在 Task 15 加 */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
