import { useEffect, useState } from "react";

import { getMatrix, type RbacMatrix } from "../api/adminRbac";

import { useStaffSession } from "./useStaffSession";

/** fetch RBAC 矩阵；任何错误（包括非 admin 403）静默回退到 null，由消费方走静态 roles 兜底。 */
export function useDynamicMenu(): { matrix: RbacMatrix | null; loading: boolean } {
  const { token, role } = useStaffSession();
  const [matrix, setMatrix] = useState<RbacMatrix | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    if (!token) {
      setMatrix(null);
      setLoading(false);
      return;
    }
    let cancelled = false;
    if (role !== "admin") {
      setLoading(false);
      return;
    }
    setLoading(true);
    getMatrix(token)
      .then((m) => {
        if (!cancelled) setMatrix(m);
      })
      .catch(() => {
        if (!cancelled) setMatrix(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [token, role]);
  return { matrix, loading };
}
