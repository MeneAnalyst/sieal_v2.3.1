import { Link, useRouterState } from "@tanstack/react-router";
import { useEffect } from "react";
import {
  LayoutDashboard, Users, Calendar, Boxes, Syringe, Network,
  BarChart3, Bot, FileClock, FileOutput, Settings, HelpCircle, Pill, Database, X,
  ChevronLeft, ChevronRight,
} from "lucide-react";
import { getUser } from "@/lib/api";
import { cn } from "@/lib/utils";

const NAV = [
  { section: "Overview", items: [{ to: "/dashboard", label: "Dashboard", icon: LayoutDashboard }] },
  { section: "Patients", items: [
    { to: "/patients", label: "Recipients of Care", icon: Users },
    { to: "/appointments", label: "Appointments", icon: Calendar },
  ]},
  { section: "Pharmacy", items: [
    { to: "/stock", label: "Stock Register", icon: Boxes },
    { to: "/dispense", label: "Dispense", icon: Syringe },
    { to: "/network", label: "Stock Network", icon: Network },
  ]},
  { section: "Analytics", items: [
    { to: "/forecast", label: "Forecast & Kanban", icon: BarChart3 },
    { to: "/ai", label: "Strategic Intelligence", icon: Bot },
    { to: "/analytics", label: "Population Analytics", icon: Database },
  ]},
  { section: "Data", items: [
    { to: "/ehr", label: "EHR Import", icon: FileClock },
    { to: "/reports", label: "Reports & Export", icon: FileOutput },
  ]},
  { section: "System", items: [
    { to: "/settings", label: "Settings", icon: Settings },
    { to: "/help", label: "Help", icon: HelpCircle },
  ]},
];

interface SidebarProps {
  mobileOpen: boolean;
  onClose: () => void;
  collapsed: boolean;
  onToggleCollapsed: () => void;
}

export function Sidebar({ mobileOpen, onClose, collapsed, onToggleCollapsed }: SidebarProps) {
  const user = getUser();
  const pathname = useRouterState({ select: (s) => s.location.pathname });

  // Auto-close the mobile drawer on every navigation — without this,
  // tapping a link leaves the drawer open over the new page underneath it.
  useEffect(() => {
    onClose();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname]);

  // Collapse only ever applies at md: and above — on mobile the drawer is
  // either fully open (full labels, for discoverability) or fully closed.
  // Width itself is driven by Tailwind classes below, not JS, so there's
  // no flash-of-wrong-width on first paint.

  return (
    <>
      {/* Backdrop — mobile only, closes the drawer on tap outside it */}
      {mobileOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 md:hidden"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      <nav
        className={cn(
          "fixed md:static inset-y-0 left-0 z-50 bg-teal-900 flex flex-col h-full overflow-y-auto overflow-x-hidden transition-[transform,width] duration-200 ease-out md:translate-x-0",
          "w-[228px] min-w-[228px]", // mobile drawer width — always full, regardless of desktop collapse state
          collapsed ? "md:w-[68px] md:min-w-[68px]" : "md:w-[228px] md:min-w-[228px]",
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        <div className={cn("px-3.5 pt-4 pb-3 border-b border-white/[0.07] flex items-center gap-2.5", collapsed && "md:px-0 md:justify-center")}>
          <div className="w-8 h-8 bg-teal-500 rounded-lg flex items-center justify-center flex-shrink-0">
            <Pill className="h-4 w-4 text-teal-950" strokeWidth={2.5} />
          </div>
          <div className={cn("flex-1", collapsed && "md:hidden")}>
            <div className="text-white font-extrabold text-sm leading-tight">SIEAL</div>
            <div className="text-teal-400 text-[9px] font-semibold uppercase tracking-wide">RESILIENCE-ART v2.0</div>
          </div>
          <button
            onClick={onClose}
            className="md:hidden w-7 h-7 rounded-md flex items-center justify-center text-white/60 hover:bg-white/10 hover:text-white flex-shrink-0"
            aria-label="Close menu"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {user && (
          <div className={cn(
            "mx-2.5 mt-2 mb-1 bg-teal-500/10 border border-teal-500/20 rounded-md px-2.5 py-1.5",
            collapsed && "md:hidden"
          )}>
            <div className="text-teal-100 text-[11px] font-semibold leading-tight">{user.facility_name}</div>
            <div className="text-teal-400 text-[10px] mono">{user.facility_dhis2}</div>
          </div>
        )}

        {NAV.map((group) => (
          <div key={group.section}>
            <div className={cn(
              "px-3 pt-2.5 pb-1 text-[9px] font-bold text-white/25 uppercase tracking-widest",
              collapsed && "md:hidden"
            )}>
              {group.section}
            </div>
            {group.items.map((item) => {
              const Icon = item.icon;
              const active = pathname.startsWith(item.to);
              return (
                <Link
                  key={item.to}
                  to={item.to}
                  title={collapsed ? item.label : undefined}
                  className={cn(
                    "flex items-center gap-2 mx-2 my-0.5 px-2.5 py-2 rounded-md text-[12px] font-medium transition-colors",
                    active ? "bg-teal-600 text-white" : "text-white/50 hover:bg-white/[0.07] hover:text-white/90",
                    collapsed && "md:justify-center md:px-0 md:mx-1.5"
                  )}
                >
                  <Icon className="h-[15px] w-[15px] flex-shrink-0" />
                  <span className={collapsed ? "md:hidden" : undefined}>{item.label}</span>
                </Link>
              );
            })}
          </div>
        ))}

        {/* Desktop-only collapse toggle — mobile drawer has no concept of collapsed */}
        <button
          onClick={onToggleCollapsed}
          className="hidden md:flex items-center justify-center gap-1.5 mx-2 mt-2 mb-1 py-1.5 rounded-md text-white/40 hover:bg-white/[0.07] hover:text-white/80 transition-colors text-[11px]"
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? <ChevronRight className="h-3.5 w-3.5" /> : <><ChevronLeft className="h-3.5 w-3.5" /> Collapse</>}
        </button>

        <div className={cn("mt-auto border-t border-white/[0.07] p-2.5", collapsed && "md:p-1.5")}>
          <Link
            to="/settings"
            title={collapsed ? (user?.full_name ?? "Account") : undefined}
            className={cn(
              "flex items-center gap-2.5 p-1.5 rounded-md hover:bg-white/[0.06] transition-colors",
              collapsed && "md:justify-center"
            )}
          >
            <div className="w-[30px] h-[30px] rounded-lg bg-teal-600 flex items-center justify-center text-white font-bold text-[11px] flex-shrink-0">
              {(user?.full_name ?? "?")[0]?.toUpperCase()}
            </div>
            <div className={cn("min-w-0", collapsed && "md:hidden")}>
              <div className="text-slate-100 text-xs font-semibold truncate">{user?.full_name ?? "..."}</div>
              <div className="text-teal-400 text-[10px] uppercase tracking-wide">{user?.role}</div>
            </div>
          </Link>
        </div>
      </nav>
    </>
  );
}
