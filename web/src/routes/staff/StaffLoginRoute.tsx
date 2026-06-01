import { useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";

import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "../../components/ui/form";
import { Input } from "../../components/ui/input";
import { useStaffSession } from "../../hooks/useStaffSession";
import { staffLogin } from "../../api/staff";

const schema = z.object({
  staff_id: z.string().min(1, "请输入工号"),
  password: z.string().min(1, "请输入密码"),
});

type FormValues = z.infer<typeof schema>;

export function StaffLoginRoute() {
  const { login } = useStaffSession();
  const nav = useNavigate();

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { staff_id: "", password: "" },
  });

  async function onSubmit(values: FormValues) {
    try {
      const { token } = await staffLogin(values.staff_id.trim(), values.password);
      login(token);
      nav("/staff/conversations");
    } catch {
      toast.error("工号或密码错误");
    }
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
          <CardTitle className="text-xl">Tevau 客服 AI 引擎</CardTitle>
          <CardDescription>客服工作台登录</CardDescription>
        </CardHeader>
        <CardContent>
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-4">
              <FormField
                control={form.control}
                name="staff_id"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>工号</FormLabel>
                    <FormControl>
                      <Input placeholder="工号" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="password"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>密码</FormLabel>
                    <FormControl>
                      <Input type="password" placeholder="密码" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <Button type="submit" disabled={form.formState.isSubmitting} className="w-full">
                {form.formState.isSubmitting ? "..." : "登录"}
              </Button>
            </form>
          </Form>
        </CardContent>
      </Card>
    </div>
  );
}
