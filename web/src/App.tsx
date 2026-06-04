import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { ErrorBoundary } from "./components/ErrorBoundary";
import { AppShell } from "./components/app-shell/AppShell";
import { ForbiddenRoute } from "./routes/ForbiddenRoute";
import { DashboardRoute } from "./routes/admin/DashboardRoute";
import { PresenceRoute } from "./routes/admin/PresenceRoute";
import { ShiftsRoute } from "./routes/admin/ShiftsRoute";
import { RbacRoute } from "./routes/admin/RbacRoute";
import { SlaRoute } from "./routes/admin/SlaRoute";
import { StaffAccountsRoute } from "./routes/admin/StaffAccountsRoute";
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
import { TicketDetailRoute } from "./routes/staff/TicketDetailRoute";
import { TicketsRoute } from "./routes/staff/TicketsRoute";
import "./styles/globals.css";

export default function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<ChatRoute />} />
          <Route path="/bu/login" element={<BuLoginRoute />} />
          <Route path="/staff/login" element={<StaffLoginRoute />} />
          {/* 旁观为全屏只读视图，不套后台布局 */}
          <Route path="/staff/conversations/:id/spectate" element={<SpectateRoute />} />
          <Route element={<AppShell />}>
            <Route path="/staff/conversations" element={<ConversationsListRoute />} />
            <Route path="/staff/conversations/:id" element={<ConversationDetailRoute />} />
            <Route path="/staff/conversations/:id/logs" element={<ConversationLogsRoute />} />
            <Route path="/staff/kpi" element={<KpiRoute />} />
            <Route path="/staff/insights" element={<InsightsRoute />} />
            <Route path="/staff/audits" element={<AuditsRoute />} />
            <Route path="/staff/tickets" element={<TicketsRoute />} />
            <Route path="/staff/tickets/:externalId" element={<TicketDetailRoute />} />
            <Route path="/admin/staff" element={<StaffAccountsRoute />} />
            <Route path="/admin/sla" element={<SlaRoute />} />
            <Route path="/admin/dashboard" element={<DashboardRoute />} />
            <Route path="/admin/rbac" element={<RbacRoute />} />
            <Route path="/admin/presence" element={<PresenceRoute />} />
            <Route path="/admin/shifts" element={<ShiftsRoute />} />
            <Route path="/403" element={<ForbiddenRoute />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </ErrorBoundary>
  );
}
