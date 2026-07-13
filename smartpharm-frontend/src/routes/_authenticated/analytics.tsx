import { createFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Database, RefreshCw, AlertTriangle, TrendingDown, Package, Repeat, ClipboardCheck, Info, PlugZap,
} from "lucide-react";
import { api } from "@/lib/api";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableHeader, TableRow, TableHead, TableBody, TableCell } from "@/components/ui/table";

export const Route = createFileRoute("/_authenticated/analytics")({
  component: AnalyticsPage,
});

const RISK_BADGE = { low: "green", medium: "amber", high: "red", critical: "red" } as const;

function AnalyticsPage() {
  const { data: status, isLoading } = useQuery({ queryKey: ["warehouse-status"], queryFn: api.warehouseStatus });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <div className="text-lg font-extrabold text-foreground flex items-center gap-2">
            <Database className="h-5 w-5 text-teal-700" /> Population Analytics
          </div>
          <div className="text-xs text-muted-foreground mt-0.5">
            Clinical, operational, strategic, optimization, and policy questions — answered from the star-schema warehouse, not live OLTP data.
          </div>
        </div>
        {status?.configured && <RefreshButton />}
      </div>

      {!isLoading && !status?.configured ? (
        <NotConnected />
      ) : (
        <Tabs defaultValue="clinical">
          <TabsList className="flex-wrap">
            <TabsTrigger value="clinical"><AlertTriangle className="h-3.5 w-3.5" /> Clinical</TabsTrigger>
            <TabsTrigger value="operational"><TrendingDown className="h-3.5 w-3.5" /> Operational</TabsTrigger>
            <TabsTrigger value="strategic"><Package className="h-3.5 w-3.5" /> Strategic</TabsTrigger>
            <TabsTrigger value="optimization"><Repeat className="h-3.5 w-3.5" /> Optimization</TabsTrigger>
            <TabsTrigger value="policy"><ClipboardCheck className="h-3.5 w-3.5" /> Policy</TabsTrigger>
          </TabsList>

          <TabsContent value="clinical"><ClinicalTab /></TabsContent>
          <TabsContent value="operational"><OperationalTab /></TabsContent>
          <TabsContent value="strategic"><StrategicTab /></TabsContent>
          <TabsContent value="optimization"><OptimizationTab /></TabsContent>
          <TabsContent value="policy"><PolicyTab /></TabsContent>
        </Tabs>
      )}
    </div>
  );
}

function RefreshButton() {
  const qc = useQueryClient();
  const mutation = useMutation({
    mutationFn: api.warehouseRefresh,
    onSuccess: () => {
      setTimeout(() => {
        qc.invalidateQueries({ queryKey: ["failure-risk"] });
        qc.invalidateQueries({ queryKey: ["stockout-forecast"] });
        qc.invalidateQueries({ queryKey: ["funding-scenario"] });
        qc.invalidateQueries({ queryKey: ["redistribution"] });
        qc.invalidateQueries({ queryKey: ["intervention-effectiveness"] });
      }, 4000);
    },
  });
  return (
    <Button variant="outline" size="sm" className="gap-1.5" onClick={() => mutation.mutate()} disabled={mutation.isPending}>
      <RefreshCw className={`h-3.5 w-3.5 ${mutation.isPending ? "animate-spin" : ""}`} />
      {mutation.isPending ? "Refreshing..." : mutation.isSuccess ? "Refresh queued" : "Refresh Warehouse"}
    </Button>
  );
}

function NotConnected() {
  return (
    <Card className="border-dashed">
      <CardContent className="flex flex-col items-center text-center py-14 px-6">
        <div className="w-12 h-12 rounded-xl bg-teal-50 border border-teal-100 flex items-center justify-center mb-3">
          <PlugZap className="h-5 w-5 text-teal-600" />
        </div>
        <div className="text-sm font-bold text-foreground mb-1">Warehouse not connected</div>
        <div className="text-xs text-muted-foreground max-w-md leading-relaxed">
          Population Analytics reads from a separate Postgres warehouse, not the live pharmacy database. Set{" "}
          <code className="mono bg-muted px-1 rounded">WAREHOUSE_DATABASE_URL</code> in <code className="mono bg-muted px-1 rounded">backend/.env</code>{" "}
          to a Postgres connection string (Supabase, Neon, or RDS all work), then run{" "}
          <code className="mono bg-muted px-1 rounded">python -m etl.build_warehouse</code> from the backend directory.
        </div>
      </CardContent>
    </Card>
  );
}

function MethodNote({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-start gap-2 rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-[11px] text-blue-800 mb-3">
      <Info className="h-3.5 w-3.5 flex-shrink-0 mt-0.5" /> <span>{children}</span>
    </div>
  );
}

// ── 1. Clinical — Who is likely to fail ART in 6 months? ────────────
function ClinicalTab() {
  const { data, isLoading, error } = useQuery({ queryKey: ["failure-risk"], queryFn: () => api.failureRisk() });
  if (isLoading) return <LoadingState />;
  if (error) return <ErrorState error={error} />;

  return (
    <Card>
      <CardHeader><CardTitle>Who is likely to fail ART in 6 months?</CardTitle></CardHeader>
      <CardContent>
        {data && <MethodNote>{data.method}</MethodNote>}
        <Table>
          <TableHeader>
            <TableRow><TableHead>Patient</TableHead><TableHead>Facility</TableHead><TableHead>Risk</TableHead><TableHead>Top Drivers</TableHead></TableRow>
          </TableHeader>
          <TableBody>
            {data?.patients.slice(0, 25).map((p) => (
              <TableRow key={p.patient_id}>
                <TableCell className="mono text-[10px]">{p.patient_id.slice(0, 8)}… <span className="text-muted-foreground">({p.age_band}, {p.distance_band})</span></TableCell>
                <TableCell>{p.facility_name}</TableCell>
                <TableCell>
                  <Badge variant={RISK_BADGE[p.risk_band]}>{p.risk_band}</Badge>{" "}
                  <span className="text-xs font-bold">{Math.round(p.risk_score_6mo * 100)}%</span>
                </TableCell>
                <TableCell className="text-[11px]">{p.top_drivers.join(", ") || "—"}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

// ── 2. Operational — Which clinic will stock out next? ──────────────
function OperationalTab() {
  const { data, isLoading, error } = useQuery({ queryKey: ["stockout-forecast"], queryFn: api.stockoutForecast });
  if (isLoading) return <LoadingState />;
  if (error) return <ErrorState error={error} />;

  return (
    <Card>
      <CardHeader><CardTitle>Which clinic will stock out next?</CardTitle></CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow><TableHead>Facility</TableHead><TableHead>Drug</TableHead><TableHead>DSR</TableHead><TableHead>ADC (7d)</TableHead><TableHead>Predicted Stockout</TableHead></TableRow>
          </TableHeader>
          <TableBody>
            {data?.facilities.slice(0, 25).map((r, i) => (
              <TableRow key={i}>
                <TableCell className="font-semibold text-foreground">{r.facility_name}</TableCell>
                <TableCell>{r.drug_name}</TableCell>
                <TableCell className="font-bold" style={{ color: r.stockout_flag ? "#EF4444" : "#10B981" }}>
                  {r.stock_days_remaining !== null ? `${r.stock_days_remaining}d` : "—"}
                </TableCell>
                <TableCell>{r.avg_daily_consumption_7d ?? "—"}</TableCell>
                <TableCell>{r.predicted_stockout_date ?? "Not imminent"}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

// ── 3. Strategic — What happens if funding drops 20%? ───────────────
function StrategicTab() {
  const { data, isLoading, error } = useQuery({ queryKey: ["funding-scenario"], queryFn: () => api.fundingScenario(-20) });
  if (isLoading) return <LoadingState />;
  if (error) return <ErrorState error={error} />;

  return (
    <Card>
      <CardHeader><CardTitle>What happens if funding drops 20%?</CardTitle></CardHeader>
      <CardContent>
        {data && <MethodNote>{data.assumption_note}</MethodNote>}
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Facility</TableHead><TableHead>Stockout Rate</TableHead><TableHead>Default Rate</TableHead>
              <TableHead>Suppression Rate</TableHead><TableHead>Patients at Risk</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data?.facilities.map((f, i) => (
              <TableRow key={i}>
                <TableCell className="font-semibold text-foreground">{f.facility_name}</TableCell>
                <TableCell>
                  {f.baseline ? `${Math.round(f.baseline.stockout_rate * 100)}% → ` : ""}
                  <span className="font-bold text-red-600">{Math.round(f.scenario.stockout_rate * 100)}%</span>
                </TableCell>
                <TableCell>
                  {f.baseline ? `${Math.round(f.baseline.default_rate * 100)}% → ` : ""}
                  <span className="font-bold text-amber-600">{Math.round(f.scenario.default_rate * 100)}%</span>
                </TableCell>
                <TableCell>
                  {f.baseline ? `${Math.round(f.baseline.suppression_rate * 100)}% → ` : ""}
                  <span className="font-bold">{Math.round(f.scenario.suppression_rate * 100)}%</span>
                </TableCell>
                <TableCell className="font-bold">{f.scenario.patients_at_risk}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

// ── 4. Optimization — Where should we redistribute drugs today? ─────
function OptimizationTab() {
  const { data, isLoading, error } = useQuery({ queryKey: ["redistribution"], queryFn: api.redistribution });
  if (isLoading) return <LoadingState />;
  if (error) return <ErrorState error={error} />;

  return (
    <Card>
      <CardHeader><CardTitle>Where should we redistribute drugs today?</CardTitle></CardHeader>
      <CardContent>
        {data && <MethodNote>{data.method}</MethodNote>}
        <Table>
          <TableHeader>
            <TableRow><TableHead>Drug</TableHead><TableHead>From</TableHead><TableHead>To</TableHead><TableHead>Qty</TableHead><TableHead>Urgency</TableHead><TableHead>Status</TableHead></TableRow>
          </TableHeader>
          <TableBody>
            {data?.recommendations.length === 0 && <TableRow><TableCell colSpan={6} className="text-center py-8 text-muted-foreground">No redistribution needed right now</TableCell></TableRow>}
            {data?.recommendations.map((r, i) => (
              <TableRow key={i}>
                <TableCell className="font-semibold text-foreground">{r.drug_name}</TableCell>
                <TableCell>{r.source_facility} <span className="text-[10px] text-muted-foreground">({r.source_surplus_days}d)</span></TableCell>
                <TableCell>{r.target_facility} <span className="text-[10px] text-muted-foreground">({r.target_days_remaining}d)</span></TableCell>
                <TableCell className="font-bold">{r.recommended_qty}</TableCell>
                <TableCell className="font-bold text-amber-600">{r.urgency_score}</TableCell>
                <TableCell><Badge variant="blue">{r.status}</Badge></TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

// ── 5. Policy — Which intervention reduces defaulting most? ─────────
function PolicyTab() {
  const { data, isLoading, error } = useQuery({ queryKey: ["intervention-effectiveness"], queryFn: api.interventionEffectiveness });
  if (isLoading) return <LoadingState />;
  if (error) return <ErrorState error={error} />;

  return (
    <Card>
      <CardHeader><CardTitle>Which intervention reduces defaulting most?</CardTitle></CardHeader>
      <CardContent>
        {data && <MethodNote>{data.method}</MethodNote>}
        <Table>
          <TableHeader>
            <TableRow><TableHead>Intervention</TableHead><TableHead>n</TableHead><TableHead>Avg. Effect Size</TableHead><TableHead>Cost per Default Averted</TableHead></TableRow>
          </TableHeader>
          <TableBody>
            {data?.interventions.map((iv, i) => (
              <TableRow key={i}>
                <TableCell className="font-semibold text-foreground">{iv.intervention_name}</TableCell>
                <TableCell>{iv.n_patients}</TableCell>
                <TableCell className="font-bold text-emerald-700">{(iv.avg_effect_size * 100).toFixed(1)} pts</TableCell>
                <TableCell>${iv.avg_cost_per_default_averted.toFixed(2)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

function LoadingState() {
  return <div className="text-center py-14 text-xs text-muted-foreground">Loading...</div>;
}
function ErrorState({ error }: { error: unknown }) {
  return (
    <div className="text-center py-10 text-xs text-red-600">
      {error instanceof Error ? error.message : "Failed to load. Has the ETL been run yet?"}
    </div>
  );
}
