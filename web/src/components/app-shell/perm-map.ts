/** path → RBAC permission_key 映射；从原 StaffLayout.tsx:80-99 搬出。 */
export const PATH_TO_PERM: Record<string, string> = {
  "/admin/dashboard": "admin.dashboard",
  "/admin/staff": "admin.staff",
  "/admin/sla": "admin.sla",
  "/admin/rbac": "admin.rbac",
  "/admin/presence": "admin.presence",
};
