import { useState, useEffect, type PropsWithChildren } from "react";
import { Sidebar } from "./Sidebar";
import { Header } from "./Header";

const COLLAPSE_KEY = "sieal_sidebar_collapsed";

export function AppShell({ children }: PropsWithChildren) {
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return localStorage.getItem(COLLAPSE_KEY) === "1";
    } catch {
      return false; // localStorage can throw in private-browsing/some embedded contexts
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem(COLLAPSE_KEY, collapsed ? "1" : "0");
    } catch {
      // non-fatal — collapse preference just won't persist across reloads
    }
  }, [collapsed]);

  return (
    <div className="flex h-screen overflow-hidden bg-muted/30">
      <Sidebar
        mobileOpen={mobileNavOpen}
        onClose={() => setMobileNavOpen(false)}
        collapsed={collapsed}
        onToggleCollapsed={() => setCollapsed((c) => !c)}
      />
      <div className="flex-1 flex flex-col overflow-hidden min-w-0">
        <Header onMenuClick={() => setMobileNavOpen(true)} />
        <main className="flex-1 overflow-y-auto p-3 md:p-5">{children}</main>
      </div>
    </div>
  );
}
