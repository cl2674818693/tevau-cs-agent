import { useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useState } from "react";

import { setIdentity } from "../api/identity";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "../components/ui/form";
import { Input } from "../components/ui/input";

/** B 端主账户 ID 登录页（spec §4.1）。后端 /api/v1/auth/bu/login 在 task-04 落地。 */

const schema = z.object({
  bu_id: z.string().min(1, "请输入主账户 ID"),
});

type FormValues = z.infer<typeof schema>;

export function BuLoginRoute() {
  const [err, setErr] = useState("");
  const nav = useNavigate();

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { bu_id: "" },
  });

  async function onSubmit(values: FormValues) {
    setErr("");
    const r = await fetch("/api/v1/auth/bu/login", {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ bu_id: values.bu_id.trim() }),
    });
    if (!r.ok) {
      setErr((await r.text()) || "主账户不存在或已禁用");
      return;
    }
    setIdentity({ kind: "b", buId: values.bu_id.trim() });
    nav("/");
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4">
      <Card className="w-full max-w-sm">
        <CardHeader className="space-y-1 text-center">
          <div className="flex justify-center">
            <div className="grid h-10 w-10 place-items-center rounded bg-primary">
              <span className="text-lg font-bold text-primary-foreground">T</span>
            </div>
          </div>
          <CardTitle className="text-xl">Tevau AI 客服</CardTitle>
          <CardDescription>合作伙伴技术支持</CardDescription>
        </CardHeader>
        <CardContent>
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-4">
              <FormField
                control={form.control}
                name="bu_id"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>主账户 ID</FormLabel>
                    <FormControl>
                      <Input
                        placeholder="主账户 ID / 租户 ID（例如 1011010000068）"
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              {err && (
                <p className="text-sm text-destructive">{err}</p>
              )}
              <Button type="submit" disabled={form.formState.isSubmitting} className="w-full">
                {form.formState.isSubmitting ? "..." : "进入对话"}
              </Button>
            </form>
          </Form>
        </CardContent>
      </Card>
    </div>
  );
}
