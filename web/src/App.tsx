import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { StaffLayout } from "./components/StaffLayout";
import { PromptsRoute } from "./routes/admin/PromptsRoute";
import { BuLoginRoute } from "./routes/BuLoginRoute";
import { ChatRoute } from "./routes/ChatRoute";
import { ConversationDetailRoute } from "./routes/staff/ConversationDetailRoute";
import { ConversationsListRoute } from "./routes/staff/ConversationsListRoute";
import { KpiRoute } from "./routes/staff/KpiRoute";
import { SpectateRoute } from "./routes/staff/SpectateRoute";
import { StaffLoginRoute } from "./routes/staff/StaffLoginRoute";
import "./styles/globals.css";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<ChatRoute />} />
        <Route path="/bu/login" element={<BuLoginRoute />} />
        <Route path="/staff/login" element={<StaffLoginRoute />} />
        <Route path="/staff/conversations/:id/spectate" element={<SpectateRoute />} />
        <Route element={<StaffLayout />}>
          <Route path="/staff/conversations" element={<ConversationsListRoute />} />
          <Route path="/staff/conversations/:id" element={<ConversationDetailRoute />} />
          <Route path="/staff/kpi" element={<KpiRoute />} />
          <Route path="/admin/prompts" element={<PromptsRoute />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
