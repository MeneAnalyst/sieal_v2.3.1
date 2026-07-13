import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Tooltip, Cell } from "recharts";
import { ShieldAlert, PhoneCall, Info, Microscope, ClipboardList } from "lucide-react";
import { api } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import { Table, TableHeader, TableRow, TableHead, TableBody, TableCell } from "@/components/ui/table";
import { ChartInterpretation, ChartLegend } from "@/components/charts/ChartLegend";
import type { DefaulterRiskPatient } from "@/types";

const RISK_META: Record<DefaulterRiskPatient["risk_band"], { color: string; barColor: string; badge: "red" | "amber" | "green" }> = {
  HIGH: { color: "text-red-700", barColor: "#EF4444", badge: "red" },
  MEDIUM: { color: "text-amber-700", barColor: "#F59E0B", badge: "amber" },
  LOW: { color: "text-emerald-700", barColor: "#10B981", badge: "green" },
};

const TRACE_METHODS = [
  { key: "PHONE_CALL", label: "Phone Call" }, { key: "SMS", label: "SMS" },
  { key: "HOME_VISIT", label: "Home Visit" }, { key: "COMMUNITY_HEALTH_WORKER", label: "Community Health Worker" },
];
const TRACE_OUTCOMES = [
  { key: "RETURNED", label: "Returned to Care" }, { key: "PROMISED_TO_RETURN", label: "Promised to Return" },
  { key: "UNREACHABLE", label: "Unreachable" }, { key: "TRANSFERRED_OUT", label: "Transferred Out" },
  { key: "DECEASED", label: "Deceased" }, { key: "REFUSED", label: "Refused Care" },
];
const REASONS = [
  { key: "TRAVEL_DISTANCE", label: "Travel Distance" }, { key: "SIDE_EFFECTS", label: "Side Effects" },
  { key: "STIGMA", label: "Stigma" }, { key: "CLINIC_WAIT_TIME", label: "Clinic Wait Time" },
  { key: "FINANCIAL_CONSTRAINTS", label: "Financial Constraints" }, { key: "FORGOT", label: "Forgot" },
  { key: "OTHER", label: "Other" },
];

export function DefaulterManagement() {
  const [traceTarget, setTraceTarget] = useState<DefaulterRiskPatient | null>(null);
  const { data: risk, isLoading } = useQuery({ queryKey: ["defaulter-risk"], queryFn: api.defaulterRisk });
  const { data: reasons } = useQuery({ queryKey: ["defaulter-reasons"], queryFn: api.defaulterReasons });

  const highRisk = risk?.patients.filter((p) => p.risk_band === "HIGH") ?? [];
  const mediumRisk = risk?.patients.filter((p) => p.risk_band === "MEDIUM") ?? [];
  const lowRisk = risk?.patients.filter((p) => p.risk_band === "LOW") ?? [];

  const chartData = (reasons?.reasons ?? []).map((r) => ({
    name: REASONS.find((x) => x.key === r.reason)?.label ?? r.reason,
    pct: r.pct,
    count: r.count,
  }));

  return (
    <Card className="overflow-hidden border-teal-100">
      <div className="bg-gradient-to-r from-teal-800 via-teal-700 to-teal-600 px-5 py-4 relative overflow-hidden">
        <div className="absolute -right-6 -top-10 w-40 h-40 rounded-full bg-white/5" />
        <div className="absolute right-16 -bottom-14 w-28 h-28 rounded-full bg-white/5" />
        <div className="relative z-10 flex items-center justify-between flex-wrap gap-3">
          <div>
            <div className="flex items-center gap-2 text-white font-extrabold text-base">
              <ShieldAlert className="h-4.5 w-4.5" /> Defaulter Management
            </div>
            <div className="text-teal-100 text-xs mt-0.5">
              Risk-stratified tracing priority for currently-engaged patients — before they become LTFU, not after.
            </div>
          </div>
          <div className="flex gap-2">
            <RiskCountPill label="High" count={highRisk.length} color="bg-red-500/90" />
            <RiskCountPill label="Medium" count={mediumRisk.length} color="bg-amber-500/90" />
            <RiskCountPill label="Low" count={lowRisk.length} color="bg-emerald-500/90" />
          </div>
        </div>
      </div>

      <CardContent className="space-y-4 pt-4">
        {risk && (
          <div className="flex items-start gap-2 rounded-lg border border-blue-200 bg-blue-50 px-3.5 py-2.5 text-[11px] text-blue-800">
            <Microscope className="h-3.5 w-3.5 flex-shrink-0 mt-0.5" />
            <div>
              <strong>Statistical method:</strong> {risk.method === "logistic_regression" ? "Logistic regression" : "Rule-based fallback (days overdue)"}
              {" — "}{risk.caveat}
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-[1.4fr_1fr] gap-4">
          <div>
            <div className="text-xs font-bold text-foreground mb-2 flex items-center gap-1.5">
              <ClipboardList className="h-3.5 w-3.5" /> Prioritized Outreach List
            </div>
            <Table>
              <TableHeader>
                <TableRow><TableHead>Patient</TableHead><TableHead>Risk</TableHead><TableHead>Overdue</TableHead><TableHead></TableHead></TableRow>
              </TableHeader>
              <TableBody>
                {isLoading && <TableRow><TableCell colSpan={4} className="text-center py-8 text-muted-foreground">Scoring cohort...</TableCell></TableRow>}
                {risk?.patients.length === 0 && <TableRow><TableCell colSpan={4} className="text-center py-8 text-muted-foreground">No at-risk patients detected</TableCell></TableRow>}
                {risk?.patients.slice(0, 12).map((p) => {
                  const meta = RISK_META[p.risk_band];
                  return (
                    <TableRow key={p.patient_id}>
                      <TableCell>
                        <div className="font-semibold text-foreground">{p.full_name}</div>
                        <div className="mono text-[10px] text-muted-foreground">{p.art_number}</div>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <Badge variant={meta.badge}>{p.risk_band}</Badge>
                          <span className={`text-xs font-bold ${meta.color}`}>{p.risk_score}%</span>
                        </div>
                        <div className="h-1.5 w-full rounded-full bg-muted mt-1 overflow-hidden">
                          <div className="h-full rounded-full" style={{ width: `${p.risk_score}%`, background: meta.barColor }} />
                        </div>
                      </TableCell>
                      <TableCell className={p.days_overdue > 0 ? "font-bold text-red-600" : "text-muted-foreground"}>
                        {p.days_overdue > 0 ? `${p.days_overdue}d` : "On track"}
                      </TableCell>
                      <TableCell>
                        <Button size="sm" variant="outline" className="h-7 text-[10px] gap-1" onClick={() => setTraceTarget(p)}>
                          <PhoneCall className="h-3 w-3" /> Log Trace
                        </Button>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
            <ChartLegend items={[
              { color: "#EF4444", label: "HIGH risk — trace within 48h" },
              { color: "#F59E0B", label: "MEDIUM risk — trace this week" },
              { color: "#10B981", label: "LOW risk — routine follow-up" },
            ]} />
            <ChartInterpretation>
              Risk score combines days overdue, adherence history, and distance to facility
              {risk?.method === "logistic_regression" ? " via a logistic regression model trained on this cohort's outcomes" : " via a rule-based fallback"}.
              The bar length under each score is a visual read of the same percentage, not a separate measure.
            </ChartInterpretation>
          </div>

          <div>
            <div className="text-xs font-bold text-foreground mb-2">Root Causes (logged trace attempts)</div>
            {chartData.length === 0 ? (
              <div className="flex items-start gap-2 rounded-lg border border-border bg-muted/40 px-3 py-3 text-[11px] text-muted-foreground">
                <Info className="h-3.5 w-3.5 flex-shrink-0 mt-0.5" />
                No trace attempts logged yet — this chart populates from real outreach data as "Log Trace" is used, not a modeled guess.
              </div>
            ) : (
              <>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={chartData} layout="vertical" margin={{ left: 8, right: 16 }}>
                  <XAxis type="number" tick={{ fontSize: 10, fill: "#64748B" }} axisLine={false} tickLine={false} unit="%" />
                  <YAxis type="category" dataKey="name" width={110} tick={{ fontSize: 10, fill: "#334155" }} axisLine={false} tickLine={false} />
                  <Tooltip formatter={(v: number, _n, p) => [`${v}% (${p.payload.count} traces)`, "Share"]} contentStyle={{ fontSize: 11, borderRadius: 8 }} />
                  <Bar dataKey="pct" radius={4} barSize={14}>
                    {chartData.map((_, i) => <Cell key={i} fill="#0D9488" fillOpacity={1 - i * 0.12} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
              <ChartInterpretation>
                Bars are ranked most-to-least common (darker = more frequent). <strong>{chartData[0]?.name}</strong> accounts
                for {chartData[0]?.pct}% of logged trace attempts — an intervention targeting this specific reason
                (e.g. transport vouchers if it's distance-related, SMS reminders if it's forgetfulness) will reach
                the largest share of at-risk patients.
              </ChartInterpretation>
            </>
            )}
          </div>
        </div>
      </CardContent>

      <LogTraceDialog patient={traceTarget} onOpenChange={(v) => !v && setTraceTarget(null)} />
    </Card>
  );
}

function RiskCountPill({ label, count, color }: { label: string; count: number; color: string }) {
  return (
    <div className={`rounded-lg ${color} px-3 py-1.5 text-white text-center min-w-[64px]`}>
      <div className="text-lg font-black leading-none">{count}</div>
      <div className="text-[9px] font-bold uppercase tracking-wide opacity-90">{label}</div>
    </div>
  );
}

function LogTraceDialog({ patient, onOpenChange }: { patient: DefaulterRiskPatient | null; onOpenChange: (v: boolean) => void }) {
  const qc = useQueryClient();
  const [method, setMethod] = useState("");
  const [outcome, setOutcome] = useState("");
  const [reason, setReason] = useState("");
  const [notes, setNotes] = useState("");

  const mutation = useMutation({
    mutationFn: () => api.logDefaulterTrace(patient!.patient_id, { trace_method: method, trace_outcome: outcome, reason_for_default: reason || undefined, notes: notes || undefined }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["defaulter-risk"] });
      qc.invalidateQueries({ queryKey: ["defaulter-reasons"] });
      qc.invalidateQueries({ queryKey: ["appointments-ltfu"] });
      setMethod(""); setOutcome(""); setReason(""); setNotes("");
      onOpenChange(false);
    },
  });

  return (
    <Dialog open={!!patient} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader><DialogTitle>Log Trace Attempt</DialogTitle></DialogHeader>
        {patient && (
          <>
            <div className="rounded-lg border border-border bg-muted/40 px-3 py-2 text-xs">
              <div className="font-semibold text-foreground">{patient.full_name}</div>
              <div className="mono text-[10px] text-muted-foreground">{patient.art_number} · {patient.risk_band} risk ({patient.risk_score}%)</div>
            </div>
            <div>
              <Label className="mb-1.5 block">Trace Method *</Label>
              <Select value={method} onValueChange={setMethod}>
                <SelectTrigger><SelectValue placeholder="How was the patient contacted?" /></SelectTrigger>
                <SelectContent>{TRACE_METHODS.map((m) => <SelectItem key={m.key} value={m.key}>{m.label}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div>
              <Label className="mb-1.5 block">Outcome *</Label>
              <Select value={outcome} onValueChange={setOutcome}>
                <SelectTrigger><SelectValue placeholder="Result of the attempt" /></SelectTrigger>
                <SelectContent>{TRACE_OUTCOMES.map((o) => <SelectItem key={o.key} value={o.key}>{o.label}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div>
              <Label className="mb-1.5 block">Reason for Default (if known)</Label>
              <Select value={reason} onValueChange={setReason}>
                <SelectTrigger><SelectValue placeholder="Patient-reported reason" /></SelectTrigger>
                <SelectContent>{REASONS.map((r) => <SelectItem key={r.key} value={r.key}>{r.label}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div><Label className="mb-1.5 block">Notes</Label><Input value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Optional" /></div>
            <Button className="w-full" disabled={!method || !outcome || mutation.isPending} onClick={() => mutation.mutate()}>
              {mutation.isPending ? "Saving..." : "Save Trace Attempt"}
            </Button>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
