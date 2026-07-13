import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CalendarDays, ChevronLeft, ChevronRight, Users } from "lucide-react";
import { api } from "@/lib/api";
import { fmtDate } from "@/lib/utils";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Table, TableHeader, TableRow, TableHead, TableBody, TableCell } from "@/components/ui/table";
import { DefaulterManagement } from "@/components/appointments/DefaulterManagement";

export const Route = createFileRoute("/_authenticated/appointments")({
  component: AppointmentsPage,
});

function shiftMonth(ym: string, delta: number): string {
  const [y, m] = ym.split("-").map(Number);
  const d = new Date(y, m - 1 + delta, 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

function AppointmentsPage() {
  const qc = useQueryClient();
  const [month, setMonth] = useState(() => {
    const n = new Date();
    return `${n.getFullYear()}-${String(n.getMonth() + 1).padStart(2, "0")}`;
  });
  const [defaulterThreshold, setDefaulterThreshold] = useState(14);
  const [drillCohort, setDrillCohort] = useState<string | null>(null);

  const { data: upcoming = [] } = useQuery({ queryKey: ["appointments-upcoming"], queryFn: () => api.appointmentsUpcoming(28) });
  const { data: ltfu = [] } = useQuery({ queryKey: ["appointments-ltfu"], queryFn: api.appointmentsLtfu });
  const { data: cohortData } = useQuery({
    queryKey: ["cohort-calendar", month, defaulterThreshold],
    queryFn: () => api.cohortCalendar(month, defaulterThreshold),
  });
  const { data: members = [] } = useQuery({
    queryKey: ["cohort-members", drillCohort],
    queryFn: () => api.cohortMembers(drillCohort!),
    enabled: !!drillCohort,
  });

  const attend = useMutation({
    mutationFn: (id: number) => api.markAttended(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["appointments-upcoming"] });
      qc.invalidateQueries({ queryKey: ["appointments-ltfu"] });
      qc.invalidateQueries({ queryKey: ["cohort-calendar"] });
      qc.invalidateQueries({ queryKey: ["cohort-members"] });
    },
  });

  const monthLabel = new Date(`${month}-01T00:00:00`).toLocaleDateString("en-GB", { month: "long", year: "numeric" });

  return (
    <div className="space-y-4">
      <div>
        <div className="text-lg font-extrabold text-foreground">Appointments</div>
        <div className="text-xs text-muted-foreground mt-0.5">{upcoming.length} due in 28 days · {ltfu.length} already LTFU</div>
      </div>

      {/* Primary component — proactive risk stratification before patients become LTFU */}
      <DefaulterManagement />

      {ltfu.length > 0 && (
        <div className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 px-3.5 py-2.5 text-xs text-red-800">
          <AlertTriangle className="h-4 w-4 flex-shrink-0 mt-0.5" />
          <div><strong>{ltfu.length} already-LTFU clients</strong> (30+ days overdue) — escalate to community health workers alongside the risk list above.</div>
        </div>
      )}

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0">
          <CardTitle className="flex items-center gap-1.5"><CalendarDays className="h-3.5 w-3.5" /> Cohort Calendar</CardTitle>
          <div className="flex items-center gap-2">
            <Button size="sm" variant="outline" className="h-7 w-7 p-0" onClick={() => setMonth((m) => shiftMonth(m, -1))}><ChevronLeft className="h-3.5 w-3.5" /></Button>
            <div className="text-xs font-semibold w-32 text-center">{monthLabel}</div>
            <Button size="sm" variant="outline" className="h-7 w-7 p-0" onClick={() => setMonth((m) => shiftMonth(m, 1))}><ChevronRight className="h-3.5 w-3.5" /></Button>
            <div className="flex items-center gap-1.5 ml-3">
              <Label className="text-[10px] text-muted-foreground whitespace-nowrap">Defaulter after</Label>
              <Input type="number" value={defaulterThreshold} onChange={(e) => setDefaulterThreshold(Number(e.target.value) || 14)} className="h-7 w-14 text-xs" />
              <span className="text-[10px] text-muted-foreground">days</span>
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          <div className="px-4 pt-2 pb-1 text-[11px] text-muted-foreground">
            Cohort = ART initiation month (e.g. a patient initiated 10 Jul 2026 belongs to <strong>JUL-2026</strong>).
            6-month = PHARMACY visit type, 3-month = CLINICAL. Click a row for the member list.
          </div>
          <div className="px-4 pb-2 flex items-center gap-2.5 text-[10px] text-muted-foreground flex-wrap">
            <span className="font-semibold text-foreground">Weekly schedule:</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-purple-500 inline-block" /> 1st–2nd of month = Statistics</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-blue-400 inline-block" /> Wednesdays = Registration</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-pink-500 inline-block" /> 1st &amp; 3rd Saturday = Peads/Infant/Adolescent</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-slate-400 inline-block" /> Sundays &amp; other Saturdays = Closed</span>
          </div>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Cohort</TableHead><TableHead>Total</TableHead>
                <TableHead>6-Month</TableHead><TableHead>3-Month</TableHead>
                <TableHead>Expected — {monthLabel}</TableHead>
                <TableHead>RTT</TableHead><TableHead>Defaulters</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(!cohortData || cohortData.cohorts.length === 0) && (
                <TableRow><TableCell colSpan={7} className="text-center py-8 text-muted-foreground">No cohorts with an ART initiation date recorded yet</TableCell></TableRow>
              )}
              {cohortData?.cohorts.map((c) => (
                <TableRow key={c.cohort} className="cursor-pointer hover:bg-muted/40" onClick={() => setDrillCohort(c.cohort)}>
                  <TableCell className="font-bold text-teal-700 mono">{c.cohort}</TableCell>
                  <TableCell className="font-semibold">{c.total_members}</TableCell>
                  <TableCell>{c.pharmacy_count}</TableCell>
                  <TableCell>{c.clinical_count}</TableCell>
                  <TableCell className="font-bold text-blue-700">{c.expected_this_month}</TableCell>
                  <TableCell>{c.rtt_count > 0 ? <Badge variant="amber">{c.rtt_count} RTT</Badge> : "—"}</TableCell>
                  <TableCell>{c.defaulter_count > 0 ? <Badge variant="red">{c.defaulter_count}</Badge> : "—"}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Dialog open={!!drillCohort} onOpenChange={(v) => !v && setDrillCohort(null)}>
        <DialogContent className="max-w-2xl">
          <DialogHeader><DialogTitle className="flex items-center gap-1.5"><Users className="h-4 w-4" /> {drillCohort} Cohort Members</DialogTitle></DialogHeader>
          <div className="max-h-96 overflow-y-auto">
            <Table>
              <TableHeader><TableRow><TableHead>ART</TableHead><TableHead>Name</TableHead><TableHead>Type</TableHead><TableHead>Status</TableHead><TableHead>Next Appt</TableHead><TableHead></TableHead></TableRow></TableHeader>
              <TableBody>
                {members.map((m) => (
                  <TableRow key={m.id} className={m.days_overdue > 0 ? "bg-red-50/50" : undefined}>
                    <TableCell className="mono text-xs">{m.art_number}</TableCell>
                    <TableCell className="font-semibold text-xs">{m.full_name}</TableCell>
                    <TableCell><Badge variant={m.visit_type === "PHARMACY" ? "default" : "gray"}>{m.visit_type}</Badge></TableCell>
                    <TableCell className="text-xs">{m.progress_status}</TableCell>
                    <TableCell className="text-xs">
                      {fmtDate(m.next_appointment)}
                      {m.days_overdue > 0 && <span className="text-red-600 font-bold ml-1">({m.days_overdue}d overdue)</span>}
                    </TableCell>
                    <TableCell><Button size="sm" variant="outline" className="h-6 text-[10px]" onClick={() => attend.mutate(m.id)}>Attended</Button></TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </DialogContent>
      </Dialog>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <CardHeader><CardTitle className="text-red-600">Already LTFU ({ltfu.length})</CardTitle></CardHeader>
          <CardContent className="p-0">
            <Table>
              <TableHeader><TableRow><TableHead>ART</TableHead><TableHead>Name</TableHead><TableHead>Due</TableHead><TableHead>Overdue</TableHead><TableHead></TableHead></TableRow></TableHeader>
              <TableBody>
                {ltfu.length === 0 && <TableRow><TableCell colSpan={5} className="text-center py-6 text-muted-foreground">No LTFU clients</TableCell></TableRow>}
                {ltfu.map((c) => (
                  <TableRow key={c.id} className="bg-red-50/50">
                    <TableCell className="mono">{c.art_number}</TableCell>
                    <TableCell className="font-semibold text-foreground">{c.full_name}</TableCell>
                    <TableCell>{fmtDate(c.next_appointment)}</TableCell>
                    <TableCell className="font-bold text-red-600">{c.days_overdue}d</TableCell>
                    <TableCell><Button size="sm" variant="outline" className="h-6 text-[10px]" onClick={() => attend.mutate(c.id)}>Attended</Button></TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>Upcoming ({upcoming.length})</CardTitle></CardHeader>
          <CardContent className="p-0">
            <Table>
              <TableHeader><TableRow><TableHead>ART</TableHead><TableHead>Name</TableHead><TableHead>Type</TableHead><TableHead>Due In</TableHead><TableHead></TableHead></TableRow></TableHeader>
              <TableBody>
                {upcoming.map((c) => {
                  const days = c.next_appointment ? Math.round((new Date(c.next_appointment + "T00:00:00").getTime() - Date.now()) / 86400000) : null;
                  return (
                    <TableRow key={c.id}>
                      <TableCell className="mono">{c.art_number}</TableCell>
                      <TableCell className="font-semibold text-foreground">{c.full_name}</TableCell>
                      <TableCell><Badge variant={c.visit_type === "PHARMACY" ? "default" : "gray"}>{c.visit_type}</Badge></TableCell>
                      <TableCell className="font-bold" style={{ color: days !== null && days <= 3 ? "#EF4444" : days !== null && days <= 7 ? "#F59E0B" : "#10B981" }}>
                        {days !== null ? `${days}d` : "—"}
                      </TableCell>
                      <TableCell><Button size="sm" variant="outline" className="h-6 text-[10px]" onClick={() => attend.mutate(c.id)}>Attended</Button></TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
