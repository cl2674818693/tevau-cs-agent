import { ArrowDown, ArrowUp, Minus } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export function KpiCard({
  label, value, delta, trend = "flat", icon: Icon,
}: {
  label: string;
  value: string | number;
  delta?: string;
  trend?: "up" | "down" | "flat";
  icon?: React.ComponentType<{ className?: string }>;
}) {
  const TrendIcon = trend === "up" ? ArrowUp : trend === "down" ? ArrowDown : Minus;
  const trendCls = trend === "up" ? "text-emerald-600 dark:text-emerald-500"
                 : trend === "down" ? "text-rose-600 dark:text-rose-500"
                 : "text-muted-foreground";
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-xs font-medium text-muted-foreground">{label}</CardTitle>
        {Icon && <Icon className="h-4 w-4 text-muted-foreground" />}
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{value}</div>
        {delta && (
          <div className={cn("mt-1 flex items-center gap-1 text-xs", trendCls)}>
            <TrendIcon className="h-3 w-3" />
            {delta}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
