import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { ErrorBoundary } from "./components/ErrorBoundary";
import { PromptsRoute } from "./routes/admin/PromptsRoute";
import { BuLoginRoute } from "./routes/BuLoginRoute";
import { ChatRoute } from "./routes/ChatRoute";
import { AuditsRoute } from "./routes/staff/AuditsRoute";
import { ConversationDetailRoute } from "./routes/staff/ConversationDetailRoute";
import { ConversationLogsRoute } from "./routes/staff/ConversationLogsRoute";
import { ConversationsListRoute } from "./routes/staff/ConversationsListRoute";
import { InsightsRoute } from "./routes/staff/InsightsRoute";
import { KpiRoute } from "./routes/staff/KpiRoute";
import { SpectateRoute } from "./routes/staff/SpectateRoute";
import { StaffLoginRoute } from "./routes/staff/StaffLoginRoute";
import "./styles/globals.css";

export default function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<ChatRoute />} />
          <Route path="/bu/login" element={<BuLoginRoute />} />
          <Route path="/staff/login" element={<StaffLoginRoute />} />
          <Route path="/staff/conversations" element={<ConversationsListRoute />} />
          <Route path="/staff/kpi" element={<KpiRoute />} />
          <Route path="/staff/insights" element={<InsightsRoute />} />
          <Route path="/staff/audits" element={<AuditsRoute />} />
          <Route path="/admin/prompts" element={<PromptsRoute />} />
          <Route path="/staff/conversations/:id" element={<ConversationDetailRoute />} />
          <Route path="/staff/conversations/:id/logs" element={<ConversationLogsRoute />} />
          <Route path="/staff/conversations/:id/spectate" element={<SpectateRoute />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </ErrorBoundary>
  );
}
