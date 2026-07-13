import { createFileRoute, redirect, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Pill, ChevronLeft } from "lucide-react";
import { api, setSession, getToken } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from "@/components/ui/select";

export const Route = createFileRoute("/login")({
  beforeLoad: () => {
    // Already authenticated — skip the login screen.
    if (getToken()) throw redirect({ to: "/dashboard" });
  },
  component: LoginPage,
});

interface FacilityOpt { id: number; name: string; dhis2_code: string; facility_type: string; district: string }

function LoginPage() {
  const navigate = useNavigate();
  const [step, setStep] = useState<1 | 2>(1);
  const [province, setProvince] = useState("");
  const [district, setDistrict] = useState("");
  const [facility, setFacility] = useState<FacilityOpt | null>(null);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const { data: provinces = [] } = useQuery({ queryKey: ["provinces"], queryFn: api.provinces });
  const { data: districts = [] } = useQuery({
    queryKey: ["districts", province],
    queryFn: () => api.districts(province),
    enabled: !!province,
  });
  const { data: facilities = [] } = useQuery({
    queryKey: ["facilities", province, district],
    queryFn: () => api.facilities(province, district),
    enabled: !!district,
  });

  async function handleLogin() {
    if (!username || !password) { setError("Enter username and password"); return; }
    setLoading(true); setError("");
    try {
      const { token, user } = await api.login(username, password, facility?.id);
      setSession(token, user);
      navigate({ to: "/dashboard" });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 flex items-center justify-center bg-gradient-to-br from-teal-950 via-teal-900 to-teal-800 overflow-hidden p-4">
      <div className="relative z-10 w-full max-w-[420px] max-h-[92vh] overflow-y-auto rounded-2xl border border-white/10 bg-white/[0.07] backdrop-blur-2xl p-6 sm:p-9">
        <div className="flex items-center justify-center gap-3 mb-1.5">
          <div className="w-9 h-9 rounded-lg bg-teal-500 flex items-center justify-center">
            <Pill className="h-[18px] w-[18px] text-teal-950" strokeWidth={2.5} />
          </div>
          <span className="text-white text-[22px] font-extrabold">SIEAL</span>
        </div>
        <div className="text-teal-300/70 text-[11px] text-center mb-7 uppercase tracking-widest">
          RESILIENCE-ART · Zimbabwe MOHCC
        </div>

        {step === 1 ? (
          <>
            <div className="mb-3">
              <Label className="text-teal-300/80 mb-1.5 block">Province</Label>
              <Select value={province} onValueChange={(v) => { setProvince(v); setDistrict(""); setFacility(null); }}>
                <SelectTrigger className="bg-white/[0.09] border-white/15 text-white"><SelectValue placeholder="— Select Province —" /></SelectTrigger>
                <SelectContent>
                  {provinces.map((p) => <SelectItem key={p.code} value={p.code}>{p.name} ({p.code})</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="mb-3">
              <Label className="text-teal-300/80 mb-1.5 block">District</Label>
              <Select value={district} disabled={!province} onValueChange={(v) => { setDistrict(v); setFacility(null); }}>
                <SelectTrigger className="bg-white/[0.09] border-white/15 text-white"><SelectValue placeholder="— Select District —" /></SelectTrigger>
                <SelectContent>
                  {districts.map((d) => <SelectItem key={d.code} value={d.code}>{d.name} ({d.code})</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="mb-4">
              <Label className="text-teal-300/80 mb-1.5 block">Health Facility</Label>
              <div className="max-h-[220px] overflow-y-auto space-y-1.5">
                {!district && <div className="text-white/30 text-xs text-center py-5">Select province and district first</div>}
                {facilities.map((f) => (
                  <button
                    key={f.id}
                    onClick={() => setFacility(f)}
                    className={`w-full text-left rounded-md border px-3 py-2.5 transition-colors ${
                      facility?.id === f.id ? "bg-teal-400/20 border-teal-400" : "bg-teal-400/[0.08] border-teal-400/20 hover:bg-teal-400/20"
                    }`}
                  >
                    <div className="text-white font-semibold text-[13px]">{f.name}</div>
                    <div className="text-teal-300/70 text-[11px] mono">{f.dhis2_code} · {f.facility_type} · {f.district}</div>
                  </button>
                ))}
              </div>
            </div>
            <Button className="w-full bg-teal-500 text-teal-950 hover:bg-teal-400 font-bold" disabled={!facility} onClick={() => setStep(2)}>
              Continue
            </Button>
          </>
        ) : (
          <>
            <button onClick={() => setStep(1)} className="flex items-center gap-1 text-teal-300/70 text-xs mb-3 hover:text-teal-200">
              <ChevronLeft className="h-3.5 w-3.5" /> Back
            </button>
            {facility && (
              <div className="bg-teal-400/10 border border-teal-400/20 rounded-lg p-3 mb-3.5">
                <div className="text-teal-300/70 text-[10px] font-bold uppercase tracking-wide">Selected Facility</div>
                <div className="text-white font-bold text-sm mt-0.5">{facility.name}</div>
                <div className="text-teal-400 text-[11px] mono">{facility.dhis2_code} · {facility.facility_type}</div>
              </div>
            )}
            {error && <div className="bg-red-500/15 border border-red-500/30 rounded-lg px-3 py-2 text-red-300 text-xs mb-3">{error}</div>}
            <div className="mb-3">
              <Label className="text-teal-300/80 mb-1.5 block">Username</Label>
              <Input value={username} onChange={(e) => setUsername(e.target.value)} placeholder="Enter username"
                className="bg-white/[0.09] border-white/15 text-white placeholder:text-white/40" />
            </div>
            <div className="mb-4">
              <Label className="text-teal-300/80 mb-1.5 block">Password</Label>
              <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleLogin()} placeholder="Enter password"
                className="bg-white/[0.09] border-white/15 text-white placeholder:text-white/40" />
            </div>
            <Button className="w-full bg-teal-500 text-teal-950 hover:bg-teal-400 font-bold" disabled={loading} onClick={handleLogin}>
              {loading ? "Signing in..." : "Sign In"}
            </Button>
          </>
        )}

        <div className="flex justify-center gap-1.5 mt-4">
          <div className={`h-2 rounded-full transition-all ${step === 1 ? "w-5 bg-teal-400" : "w-2 bg-white/20"}`} />
          <div className={`h-2 rounded-full transition-all ${step === 2 ? "w-5 bg-teal-400" : "w-2 bg-white/20"}`} />
        </div>
        <div className="text-center mt-3.5 text-white/30 text-[10px]">
          Demo: pharmacist / pharm123 &nbsp;|&nbsp; admin / admin123
        </div>
      </div>
    </div>
  );
}
