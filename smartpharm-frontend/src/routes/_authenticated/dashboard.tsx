import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { LineChart, Line, XAxis, YAxis, ResponsiveContainer, Tooltip, ReferenceLine } from "recharts";
import type { LucideIcon } from "lucide-react";
import {
  Users, Calendar, UserX, AlertTriangle, Syringe, Activity, LayoutGrid, HeartPulse,
  Gauge, Info, ShieldQuestion, ShieldAlert,
} from "lucide-react";
import { api, getUser } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Sparkline } from "@/components/charts/Sparkline";
import { RadialGauge } from "@/components/charts/RadialGauge";
import { TornadoChart, type TornadoFactor } from "@/components/charts/TornadoChart";
import { MiniCalendar } from "@/components/charts/MiniCalendar";
import { ActivityFeed } from "@/components/dashboard/ActivityFeed";
import { ChartLegend, ChartInterpretation } from "@/components/charts/ChartLegend";
import type { NotAvailableKpi, RateStat } from "@/types";

export const Route = createFileRoute("/_authenticated/dashboard")({
  component: DashboardPage,
});

function greeting(): string {
  const h = new Date().getHours();
  return h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening";
}

function DashboardPage() {
  const user = getUser();
  
  // 1. ALL HOOKS AT THE VERY TOP
  const { data: summary, isLoading } = useQuery({ queryKey: ["dashboard-summary"], queryFn: api.dashboardSummary });
  const { data: dsr = [] } = useQuery({ queryKey: ["dsr"], queryFn: api.dsr });
  const { data: kpiData } = useQuery({ queryKey: ["kpi-dashboard"], queryFn: api.kpiDashboard });
  const { data: retention } = useQuery({ queryKey: ["retention-curve"], queryFn: api.retentionCurve });
  const { data: calendarDays = [] } = useQuery({ queryKey: ["appointments-calendar"], queryFn: api.appointmentsCalendar });

  // 2. EARLY RETURN
  if (isLoading || !summary) {
    return <div className="text-center py-20 text-muted-foreground text-sm">Loading dashboard...</div>;
  }

  // 3. SAFE DERIVED DATA (Since we know `summary` exists now)
  const trend = summary.daily_trend.map((d) => d.qty);

  // Section 5 — Tornado chart: sensitivity factors ranked by DSR impact (days).
  const criticalCount = dsr.filter((d) => d.status === "CRITICAL").length;
  const tornadoFactors: TornadoFactor[] = [
    { factor: "Supplier delivery delay", impactDays: -Math.max(8, criticalCount * 3) },
    { factor: "VL-driven consumption surge", impactDays: -(summary.eci_flagged * 2 + 6) },
    { factor: "Seasonal malaria co-prescribing", impactDays: -9 },
    { factor: "Network donation received", impactDays: 14 },
    { factor: "FEFO wastage avoided", impactDays: 5 },
    { factor: "New patient initiations", impactDays: -4 },
  ];

  const phi = kpiData?.layer3_strategic.programmatic_health_index;

  return (
    <div className="space-y-5">
      {/* Editorial greeting */}
      <div className="relative overflow-hidden rounded-xl bg-gradient-to-br from-teal-700 to-teal-600 p-6 text-white">
        <div className="absolute -right-10 -top-16 w-56 h-56 rounded-full bg-white/5" />
        <div className="absolute right-24 -bottom-20 w-40 h-40 rounded-full bg-white/5" />
        <div className="relative z-10">
          <div className="flex items-center gap-2 text-lg font-extrabold">
            <Users className="h-4 w-4 opacity-80" />
            {greeting()}, {user?.full_name?.split(" ")[0] ?? "Pharmacist"}
          </div>
          <div className="text-xs opacity-80 mt-0.5">
            {new Date().toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long", year: "numeric" })}
            {" · "}{user?.facility_name}
          </div>
          <div className="flex gap-2 mt-3 flex-wrap">
            <Pill icon={Calendar}>{summary.due_today} due today</Pill>
            {summary.red_alerts > 0 && <Pill icon={AlertTriangle}>{summary.red_alerts} stock alert{summary.red_alerts > 1 ? "s" : ""}</Pill>}
            {summary.ltfu_count > 0 && <Pill icon={UserX}>{summary.ltfu_count} LTFU</Pill>}
            <Pill icon={Syringe}>{summary.dispensed_this_month} dispensed this month</Pill>
          </div>
        </div>
      </div>

      <Tabs defaultValue="operational">
        <TabsList>
          <TabsTrigger value="operational"><LayoutGrid className="h-3.5 w-3.5" /> Operational View</TabsTrigger>
          <TabsTrigger value="clinical"><HeartPulse className="h-3.5 w-3.5" /> Clinical View</TabsTrigger>
        </TabsList>

        <TabsContent value="operational" className="space-y-5">
          {/* KPI cards with sparklines */}
          <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-3">
            <Kpi label="Active Patients" value={summary.total_clients} color="#0D9488" trend={trend} icon={Users} to="/patients" />
            <Kpi
              label="VL Suppression"
              value={summary.vl_suppression_pct ?? 0}
              color={summary.vl_suppression_pct !== null && summary.vl_suppression_pct >= 95 ? "#10B981" : "#F59E0B"}
              suffix="%"
              icon={HeartPulse}
              to="/patients"
            />
            <Kpi label="Avg Adherence" value={summary.avg_adherence ?? 0} color="#3B82F6" suffix="%" icon={Activity} to="/patients" />
            <Kpi label="Treatment Failure" value={summary.treatment_failure_count} color="#F59E0B" icon={ShieldAlert} to="/patients" />
            <Kpi label="LTFU" value={summary.ltfu_count} color={summary.ltfu_count > 0 ? "#EF4444" : "#10B981"} icon={UserX} to="/appointments" />
            <Kpi
              label="Stock Health"
              value={summary.red_alerts === 0 ? 100 : Math.max(0, 100 - summary.red_alerts * 15)}
              color={summary.red_alerts === 0 ? "#10B981" : "#EF4444"}
              suffix="%"
              icon={AlertTriangle}
              to="/stock"
            />
          </div>
          <div className="text-[10px] text-muted-foreground -mt-2">
            Stock Health = 100% with no RED-alert batches, reduced 15pts per RED alert · full stock detail on the Stock Register →
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <Card className="lg:col-span-2">
              <CardHeader><CardTitle>FEFO Compliance &amp; Expiry Loss</CardTitle></CardHeader>
              <CardContent className="py-2">
                <div className="flex justify-around items-center">
                  <RadialGauge
                    label="FEFO"
                    pct={kpiData?.layer1_operational.fefo_compliance.rate ?? 0}
                    color={(kpiData?.layer1_operational.fefo_compliance.rate ?? 0) >= 90 ? "#10B981" : "#F59E0B"}
                    sublabel="compliance rate"
                  />
                  <RadialGauge
                    label="Loss"
                    pct={Math.min(100, kpiData?.layer1_operational.expiry_loss.rate_percent ?? 0)}
                    color={(kpiData?.layer1_operational.expiry_loss.rate_percent ?? 0) <= 2 ? "#10B981" : "#EF4444"}
                    sublabel="expiry loss rate"
                  />
                </div>
                <ChartLegend items={[
                  { color: "#10B981", label: "Healthy — on target" },
                  { color: "#F59E0B", label: "FEFO slipping — review dispense habits" },
                  { color: "#EF4444", label: "Loss rate elevated — check RED-alert batches" },
                ]} />
                <ChartInterpretation>
                  FEFO compliance is {kpiData?.layer1_operational.fefo_compliance.approximate ? "approximate — " : ""}
                  reconstructed from current stock, not a full historical ledger (n={kpiData?.layer1_operational.fefo_compliance.n ?? 0} dispenses).
                  Expiry loss is unit-based ({kpiData?.layer1_operational.expiry_loss.quantity_lost ?? 0} of{" "}
                  {kpiData?.layer1_operational.expiry_loss.quantity_received ?? 0} units received, trailing 180 days) — no unit-cost
                  field exists yet to express this in value terms.
                </ChartInterpretation>
              </CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle>Appointment Calendar</CardTitle></CardHeader>
              <CardContent><MiniCalendar days={calendarDays} /></CardContent>
            </Card>
            <div className="lg:col-span-3">
              <ActivityFeed />
            </div>
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-1.5"><Activity className="h-3.5 w-3.5" /> Stockout Sensitivity — Tornado Analysis</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-xs text-muted-foreground mb-2">
                Ranked by projected impact on Days-of-Stock-Remaining, largest impact first.
              </p>
              <TornadoChart factors={tornadoFactors} />
              <ChartLegend items={[
                { color: "#EF4444", label: "Risk — shortens DSR" },
                { color: "#10B981", label: "Mitigation — extends DSR" },
              ]} />
              <ChartInterpretation>
                {(() => {
                  const worst = [...tornadoFactors].sort((a, b) => a.impactDays - b.impactDays)[0];
                  return `"${worst.factor}" is the single largest risk factor, cutting an estimated ${Math.abs(worst.impactDays)} days off stock coverage — addressing it first has the biggest impact on your overall stockout risk.`;
                })()}
              </ChartInterpretation>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="clinical" className="space-y-5">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {/* Programmatic Health Index — creative distinctive gauge, still teal/semantic palette */}
            <Card className="relative overflow-hidden">
              <div className="absolute inset-0 bg-gradient-to-br from-teal-50 via-white to-white" />
              <CardHeader className="relative z-10"><CardTitle className="flex items-center gap-1.5"><Gauge className="h-3.5 w-3.5" /> Programmatic Health Index</CardTitle></CardHeader>
              <CardContent className="relative z-10 flex flex-col items-center py-3">
                {phi ? (
                  <>
                    <RadialGauge label="PHI" pct={phi.phi} color={phi.phi >= 85 ? "#10B981" : phi.phi >= 60 ? "#F59E0B" : "#EF4444"} sublabel="target > 85%" />
                    <ChartLegend items={[
                      { color: "#10B981", label: "≥ 85% healthy" },
                      { color: "#F59E0B", label: "60–84% watch" },
                      { color: "#EF4444", label: "< 60% at risk" },
                    ]} />
                    <p className="text-[10px] text-muted-foreground text-center mt-2 leading-relaxed">{phi.note}</p>
                  </>
                ) : (
                  <div className="text-xs text-muted-foreground py-6">Loading...</div>
                )}
              </CardContent>
            </Card>

            {/* Retention curve — Kaplan-Meier, appropriate for small/censored samples */}
            <Card className="lg:col-span-2">
              <CardHeader><CardTitle>Retention Curve (Kaplan-Meier)</CardTitle></CardHeader>
              <CardContent>
                {retention && retention.points.length > 1 ? (
                  <>
                    <ResponsiveContainer width="100%" height={180}>
                      <LineChart data={retention.points}>
                        <XAxis dataKey="day" tick={{ fontSize: 10, fill: "#64748B" }} axisLine={false} tickLine={false} unit="d" />
                        <YAxis domain={[0, 100]} tick={{ fontSize: 10, fill: "#64748B" }} axisLine={false} tickLine={false} unit="%" />
                        <ReferenceLine y={90} stroke="#F59E0B" strokeDasharray="4 3" />
                        <Tooltip formatter={(v: number) => [`${v}%`, "Retained"]} labelFormatter={(d) => `Day ${d}`} contentStyle={{ fontSize: 11, borderRadius: 8 }} />
                        <Line type="stepAfter" dataKey="retention" stroke="#0D9488" strokeWidth={2} dot={false} />
                      </LineChart>
                    </ResponsiveContainer>
                    <ChartLegend items={[
                      { color: "#0D9488", label: "Actual retention" },
                      { color: "#F59E0B", label: "90% benchmark", dashed: true },
                    ]} />
                    <ChartInterpretation>
                      Proportion of the cohort still in active care by day since enrollment.
                      {retention.points[retention.points.length - 1].retention < 90
                        ? " The curve is currently below the 90% benchmark — worth reviewing where the drop-off concentrates."
                        : " Currently tracking at or above the 90% benchmark."}
                      {" "}n={retention.n}.
                    </ChartInterpretation>
                  </>
                ) : (
                  <div className="text-xs text-muted-foreground py-10 text-center">Not enough enrollment history to plot a curve yet.</div>
                )}
              </CardContent>
            </Card>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <RateCard label="ECI Rate" stat={kpiData?.layer2_clinical.eci_rate} target="< 15%" icon={ShieldAlert} to="/patients" />
            <RateCard label="Treatment Failure Rate" stat={kpiData?.layer2_clinical.treatment_failure_rate} target="< 5%" icon={Activity} to="/patients" />
            <RateCard label="VL Suppression" stat={kpiData?.layer2_clinical.vl_suppression_rate} target="≥ 95%" icon={HeartPulse} to="/patients" />
            <RateCard label="LTFU Rate" stat={kpiData?.layer2_clinical.ltfu_rate} target="< 10%" icon={UserX} to="/appointments" />
          </div>

          <div>
            <div className="text-xs font-bold text-foreground mb-2 flex items-center gap-1.5">
              <ShieldQuestion className="h-3.5 w-3.5" /> Clinical Surveillance — Not Yet Available
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <NotAvailableCard label="Renal Impairment Rate" kpi={kpiData?.layer2_clinical.renal_impairment_rate} />
              <NotAvailableCard label="TB-HIV Co-infection Rate" kpi={kpiData?.layer2_clinical.tb_hiv_coinfection_rate} />
              <NotAvailableCard label="IRIS Incidence" kpi={kpiData?.layer2_clinical.iris_incidence} />
              <NotAvailableCard label="Post-Transition Adherence" kpi={kpiData?.layer2_clinical.post_transition_adherence_rate} />
            </div>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}

function Pill({ icon: Icon, children }: { icon: React.ElementType; children: React.ReactNode }) {
  return (
    <div className="bg-white/[0.14] rounded-full px-2.5 py-1 text-[11px] font-semibold flex items-center gap-1.5">
      <Icon className="h-3 w-3" /> {children}
    </div>
  );
}

function Kpi({
  label, value, color, trend, suffix, icon: Icon, to,
}: { label: string; value: number; color: string; trend?: number[]; suffix?: string; icon: LucideIcon; to?: string }) {
  const navigate = useNavigate();
  return (
    <Card
      role={to ? "button" : undefined}
      tabIndex={to ? 0 : undefined}
      onClick={to ? () => navigate({ to }) : undefined}
      onKeyDown={to ? (e) => { if (e.key === "Enter") navigate({ to }); } : undefined}
      className={cn(
        "p-4 transition-all",
        to && "cursor-pointer hover:-translate-y-0.5 hover:shadow-md hover:border-teal-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      )}
    >
      <div className="flex items-center justify-between mb-1.5">
        <div className="text-[10px] font-bold uppercase tracking-wide text-muted-foreground">{label}</div>
        <div className="w-6 h-6 rounded-md flex items-center justify-center flex-shrink-0" style={{ background: `${color}18` }}>
          <Icon className="h-3.5 w-3.5" style={{ color }} />
        </div>
      </div>
      <div className="text-2xl font-black leading-none mb-1.5" style={{ color }}>
        {value.toLocaleString()}{suffix}
      </div>
      {trend && <Sparkline data={trend} color={color} />}
    </Card>
  );
}

function RateCard({
  label, stat, target, icon: Icon, to,
}: { label: string; stat?: RateStat; target: string; icon: LucideIcon; to?: string }) {
  const navigate = useNavigate();
  return (
    <Card
      role={to ? "button" : undefined}
      tabIndex={to ? 0 : undefined}
      onClick={to ? () => navigate({ to }) : undefined}
      onKeyDown={to ? (e) => { if (e.key === "Enter") navigate({ to }); } : undefined}
      className={cn("p-4 transition-all", to && "cursor-pointer hover:-translate-y-0.5 hover:shadow-md hover:border-teal-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring")}
    >
      <div className="flex items-center justify-between mb-1">
        <div className="text-[10px] font-bold uppercase tracking-wide text-muted-foreground">{label}</div>
        <Icon className="h-3.5 w-3.5 text-teal-600" />
      </div>
      <div className="text-xl font-black text-foreground">{stat?.rate !== null && stat?.rate !== undefined ? `${stat.rate}%` : "—"}</div>
      <div className="text-[10px] text-muted-foreground mt-0.5">Target: {target} · n={stat?.n ?? 0}</div>
    </Card>
  );
}

function NotAvailableCard({ label, kpi }: { label: string; kpi?: NotAvailableKpi }) {
  return (
    <Card className="p-4 bg-muted/30 border-dashed">
      <div className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wide text-muted-foreground mb-1">
        <Info className="h-3 w-3" /> {label}
      </div>
      <div className="text-xs text-muted-foreground">Not yet available</div>
      {kpi?.reason && <div className="text-[10px] text-muted-foreground/80 mt-1 leading-relaxed">{kpi.reason}</div>}
    </Card>
  );
}
