import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { ShieldCheck, KeyRound, Bot, LogOut } from "lucide-react";
import { api, clearSession, getUser } from "@/lib/api";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export const Route = createFileRoute("/_authenticated/settings")({
  component: SettingsPage,
});

function SettingsPage() {
  const user = getUser();
  const navigate = useNavigate();
  const [pinMsg, setPinMsg] = useState("");
  const [newPin, setNewPin] = useState("");
  const [confirmPin, setConfirmPin] = useState("");

  function updatePin() {
    if (newPin.length !== 4) return setPinMsg("PIN must be exactly 4 digits");
    if (newPin !== confirmPin) return setPinMsg("PINs do not match");
    setPinMsg("PIN updated — use the new PIN for QR scanning");
    setNewPin(""); setConfirmPin("");
  }

  async function handleLogout() {
    await api.logout().catch(() => {});
    clearSession();
    navigate({ to: "/login" });
  }

  return (
    <div className="space-y-4 max-w-3xl">
      <div className="text-lg font-extrabold text-foreground">Settings</div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card>
          <CardHeader><CardTitle>Profile</CardTitle></CardHeader>
          <CardContent className="space-y-2.5">
            <div><Label className="mb-1">Full Name</Label><Input defaultValue={user?.full_name} /></div>
            <div><Label className="mb-1">Username</Label><Input defaultValue={user?.username} readOnly className="bg-muted" /></div>
            <div><Label className="mb-1">Role</Label><Input defaultValue={user?.role} readOnly className="bg-muted" /></div>
            <div><Label className="mb-1">Facility</Label><Input defaultValue={user?.facility_name} readOnly className="bg-muted" /></div>
          </CardContent>
        </Card>

        <Card className="border-t-[3px] border-t-teal-700">
          <CardHeader><CardTitle className="flex items-center gap-1.5"><KeyRound className="h-3.5 w-3.5" /> QR Scanner PIN</CardTitle></CardHeader>
          <CardContent className="space-y-2.5">
            <p className="text-[11px] text-muted-foreground">4-digit PIN activates a secure 5-minute scan session. All scans are logged.</p>
            <div><Label className="mb-1">New PIN</Label><Input type="password" maxLength={4} value={newPin} onChange={(e) => setNewPin(e.target.value)} /></div>
            <div><Label className="mb-1">Confirm PIN</Label><Input type="password" maxLength={4} value={confirmPin} onChange={(e) => setConfirmPin(e.target.value)} /></div>
            <Button size="sm" onClick={updatePin}>Update PIN</Button>
            {pinMsg && <div className="text-[11px] text-muted-foreground">{pinMsg}</div>}
          </CardContent>
        </Card>
      </div>

      <Card className="border-t-[3px] border-t-blue-500">
        <CardHeader><CardTitle className="flex items-center gap-1.5"><Bot className="h-3.5 w-3.5" /> AI Agent — API Key</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <div className="flex gap-2 rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-[11px] text-blue-800">
            <ShieldCheck className="h-4 w-4 flex-shrink-0 mt-0.5" />
            <span>Set the key as a backend environment variable — never in this UI or the frontend bundle.</span>
          </div>
          <div>
            <div className="text-xs font-bold text-foreground mb-1">backend/.env</div>
            <code className="mono text-[11px] block bg-teal-50 border border-teal-100 rounded px-2.5 py-2 text-teal-800">
              ANTHROPIC_API_KEY=sk-ant-your-key
            </code>
          </div>
          <div className="text-[10px] text-muted-foreground">Restart <code className="mono">uvicorn main:app --reload</code> after editing. Demo responses work without a key.</div>
        </CardContent>
      </Card>

      <div className="text-center">
        <Button variant="destructive" size="sm" className="gap-1.5" onClick={handleLogout}>
          <LogOut className="h-3.5 w-3.5" /> Sign Out
        </Button>
      </div>
    </div>
  );
}
