import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { ErrorBoundary } from "./components/ErrorBoundary";
import { StaffLayout } from "./components/StaffLayout";
import { AuditCenterRoute } from "./routes/admin/AuditCenterRoute";
import { CostRoute } from "./routes/admin/CostRoute";
import { DashboardRoute } from "./routes/admin/DashboardRoute";
import { PresenceRoute } from "./routes/admin/PresenceRoute";
import { ShiftsRoute } from "./routes/admin/ShiftsRoute";
import { PromptsRoute } from "./routes/admin/PromptsRoute";
import { QaReviewRoute } from "./routes/admin/QaReviewRoute";
import { RbacRoute } from "./routes/admin/RbacRoute";
import { RoutingRulesRoute } from "./routes/admin/RoutingRulesRoute";
import { SlaRoute } from "./routes/admin/SlaRoute";
import { StaffAccountsRoute } from "./routes/admin/StaffAccountsRoute";
import { StaffGroupsRoute } from "./routes/admin/StaffGroupsRoute";
import { StaffPerformanceRoute } from "./routes/admin/StaffPerformanceRoute";
import { ToolPoliciesRoute } from "./routes/admin/ToolPoliciesRoute";
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
          <Route element={<StaffLayout />}>
            <Route path="/staff/conversations" element={<ConversationsListRoute />} />
            <Route path="/staff/conversations/:id" element={<ConversationDetailRoute />} />
            <Route path="/staff/conversations/:id/logs" element={<ConversationLogsRoute />} />
            <Route path="/staff/kpi" element={<KpiRoute />} />
            <Route path="/staff/insights" element={<InsightsRoute />} />
            <Route path="/staff/audits" element={<AuditsRoute />} />
            <Route path="/staff/tickets" element={<TicketsRoute />} />
            <Route path="/staff/tickets/:externalId" element={<TicketDetailRoute />} />
            <Route path="/admin/prompts" element={<PromptsRoute />} />
            <Route path="/admin/staff" element={<StaffAccountsRoute />} />
            <Route path="/admin/sla" element={<SlaRoute />} />
            <Route path="/admin/audit" element={<AuditCenterRoute />} />
            <Route path="/admin/dashboard" element={<DashboardRoute />} />
            <Route path="/admin/qa" element={<QaReviewRoute />} />
            <Route path="/admin/performance" element={<StaffPerformanceRoute />} />
            <Route path="/admin/performance/:staffId" element={<StaffPerformanceRoute />} />
            <Route path="/admin/tools" element={<ToolPoliciesRoute />} />
            <Route path="/admin/cost" element={<CostRoute />} />
            <Route path="/admin/rbac" element={<RbacRoute />} />
            <Route path="/admin/staff-groups" element={<StaffGroupsRoute />} />
            <Route path="/admin/presence" element={<PresenceRoute />} />
            <Route path="/admin/shifts" element={<ShiftsRoute />} />
            <Route path="/admin/routing" element={<RoutingRulesRoute />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </ErrorBoundary>
  );
}
