/** path → RBAC permission_key 映射；从原 StaffLayout.tsx:80-99 搬出。 */
export const PATH_TO_PERM: Record<string, string> = {
  "/admin/dashboard": "admin.dashboard",
  "/admin/staff": "admin.staff",
  "/admin/sla": "admin.sla",
  "/admin/tools": "admin.tools",
  "/admin/prompts": "admin.prompts",
  "/admin/rbac": "admin.rbac",
  "/admin/staff-groups": "admin.staff_groups",
  "/admin/presence": "admin.presence",
  "/admin/shifts": "admin.shifts",
  "/admin/routing": "admin.routing",
  "/admin/prompt-editor": "admin.prompt_editor",
  "/admin/knowledge": "admin.knowledge",
  "/admin/guardrails": "admin.guardrails",
};
