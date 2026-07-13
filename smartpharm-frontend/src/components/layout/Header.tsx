import { Search, Bell, HelpCircle, Settings, LogOut, Menu } from "lucide-react";
import { useRouterState, useNavigate } from "@tanstack/react-router";
import { getUser, clearSession, api } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

const TITLES: Record<string, string> = {
  dashboard: "Dashboard", patients: "Recipients of Care", appointments: "Appointments",
  stock: "Stock Register", dispense: "Dispense", network: "Stock Network",
  forecast: "Forecast & Kanban", ai: "Strategic Intelligence", ehr: "EHR Import",
  analytics: "Population Analytics",
  reports: "Reports & Export", settings: "Settings", help: "Help",
};

interface HeaderProps {
  onMenuClick: () => void;
}

export function Header({ onMenuClick }: HeaderProps) {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const navigate = useNavigate();
  const user = getUser();
  const segment = pathname.split("/").filter(Boolean)[0] ?? "dashboard";

  async function handleLogout() {
    await api.logout().catch(() => {});
    clearSession();
    navigate({ to: "/login" });
  }

  return (
    <header className="h-[54px] bg-white border-b border-border flex items-center px-3 md:px-5 gap-2 md:gap-3 flex-shrink-0 shadow-sm">
      <Button
        variant="outline"
        size="icon"
        className="h-8 w-8 md:hidden flex-shrink-0"
        onClick={onMenuClick}
        aria-label="Open menu"
      >
        <Menu className="h-4 w-4" />
      </Button>

      <div className="flex items-center gap-1.5 flex-1 min-w-0">
        <span className="text-primary text-xs font-semibold hidden sm:inline">SIEAL</span>
        <span className="text-slate-300 hidden sm:inline">/</span>
        <span className="text-foreground text-[13px] font-bold truncate">{TITLES[segment] ?? segment}</span>
      </div>

      <div className="relative hidden md:block">
        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-400" />
        <Input placeholder="Search patients, ART numbers..." className="pl-8 h-8 w-[200px] text-xs bg-muted/60" />
      </div>

      <Button variant="outline" size="icon" className="h-8 w-8 hidden sm:inline-flex"><Bell className="h-4 w-4" /></Button>
      <Button variant="outline" size="icon" className="h-8 w-8 hidden sm:inline-flex" onClick={() => navigate({ to: "/help" })}><HelpCircle className="h-4 w-4" /></Button>
      <Button variant="outline" size="icon" className="h-8 w-8 hidden sm:inline-flex" onClick={() => navigate({ to: "/settings" })}><Settings className="h-4 w-4" /></Button>
      <button
        onClick={handleLogout}
        title="Sign out"
        className="w-8 h-8 rounded-md bg-teal-700 text-white font-bold text-[11px] flex items-center justify-center border-2 border-teal-200 hover:bg-teal-800 flex-shrink-0"
      >
        {(user?.full_name ?? "?")[0]?.toUpperCase() ?? <LogOut className="h-3.5 w-3.5" />}
      </button>
    </header>
  );
}
