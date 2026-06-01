import { Lock } from "lucide-react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";

export function ForbiddenRoute() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 p-8 text-center">
      <Lock className="h-12 w-12 text-muted-foreground" />
      <h1 className="text-lg font-semibold">403 · 无权限</h1>
      <p className="text-sm text-muted-foreground">您当前角色无法访问此页面</p>
      <Button asChild variant="outline" size="sm">
        <Link to="/staff/conversations">返回工作台</Link>
      </Button>
    </div>
  );
}
