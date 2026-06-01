import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import * as z from "zod";

import { setRollout } from "../../api/admin";
import { Button } from "../../components/ui/button";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "../../components/ui/form";
import { Input } from "../../components/ui/input";
import {
  Sheet,
  SheetContent,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "../../components/ui/sheet";
import type { PromptRow } from "./PromptsRoute.columns";

// ── Schema ────────────────────────────────────────────────────────────────────

const rolloutSchema = z.object({
  pct: z.number().min(0, "不能小于 0").max(100, "不能超过 100"),
});
type RolloutFormValues = z.infer<typeof rolloutSchema>;

// ── Types ─────────────────────────────────────────────────────────────────────

type Props = {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  row: PromptRow | null;
  token: string;
  currentRollout: Record<string, number>;
  onSuccess: (next: Record<string, number>) => void;
};

// ── Form body ─────────────────────────────────────────────────────────────────

function RolloutFormBody({
  row,
  currentRollout,
  form,
  onClose,
}: {
  row: PromptRow | null;
  currentRollout: Record<string, number>;
  form: ReturnType<typeof useForm<RolloutFormValues>>;
  onClose: () => void;
}) {
  const total = Object.values(currentRollout).reduce((a, b) => a + (b || 0), 0);
  return (
    <>
      <div className="flex-1 space-y-5 px-6 py-5">
        <div className="rounded-md bg-muted/50 px-4 py-3 text-sm text-muted-foreground">
          <p>当前所有版本合计：<span className="font-medium text-foreground">{total}%</span></p>
          <p className="mt-1 text-xs">余量自动回落到 default 版本</p>
        </div>
        <FormField
          control={form.control}
          name="pct"
          render={({ field }) => (
            <FormItem>
              <FormLabel>流量比例（%）— <span className="font-mono">{row?.version}</span></FormLabel>
              <FormControl>
                <Input
                  type="number"
                  min={0}
                  max={100}
                  aria-label={`${row?.version} 灰度比例`}
                  {...field}
                  onChange={(e) => field.onChange(Number(e.target.value))}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
      </div>
      <SheetFooter className="border-t px-6 py-4">
        <Button type="button" variant="outline" onClick={onClose}>取消</Button>
        <Button type="submit" disabled={form.formState.isSubmitting}>保存</Button>
      </SheetFooter>
    </>
  );
}

// ── Sheet ─────────────────────────────────────────────────────────────────────

export function RolloutSheet({ open, onOpenChange, row, token, currentRollout, onSuccess }: Props) {
  const form = useForm<RolloutFormValues>({
    resolver: zodResolver(rolloutSchema),
    defaultValues: { pct: 0 },
  });

  useEffect(() => {
    if (open && row) form.reset({ pct: row.rollout });
  }, [open, row, form]);

  async function onSubmit(values: RolloutFormValues) {
    if (!row) return;
    const next = { ...currentRollout, [row.version]: values.pct };
    const total = Object.values(next).reduce((a, b) => a + (b || 0), 0);
    if (total > 100) {
      form.setError("pct", { message: `合计将达 ${total}%，超过 100` });
      return;
    }
    try {
      const saved = await setRollout(token, next);
      toast.success("已保存并热加载");
      onSuccess(saved);
      onOpenChange(false);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "保存失败");
    }
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="flex flex-col gap-0 p-0">
        <SheetHeader className="border-b px-6 py-4">
          <SheetTitle>调整流量 — {row?.version}</SheetTitle>
        </SheetHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-1 flex-col overflow-y-auto">
            <RolloutFormBody row={row} currentRollout={currentRollout} form={form} onClose={() => onOpenChange(false)} />
          </form>
        </Form>
      </SheetContent>
    </Sheet>
  );
}
