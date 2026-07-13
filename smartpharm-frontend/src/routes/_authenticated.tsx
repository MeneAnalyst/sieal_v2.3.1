import { createFileRoute, redirect, Outlet } from "@tanstack/react-router";
import { getToken } from "@/lib/api";
import { AppShell } from "@/components/layout/AppShell";

export const Route = createFileRoute("/_authenticated")({
  beforeLoad: ({ location }) => {
    if (!getToken()) {
      throw redirect({ to: "/login", search: { redirect: location.href } });
    }
  },
  component: () => (
    <AppShell>
      <Outlet />
    </AppShell>
  ),
});
