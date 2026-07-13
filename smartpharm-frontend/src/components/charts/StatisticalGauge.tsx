import { TrendingUp, TrendingDown, Minus, AlertTriangle } from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { RadialGauge } from "@/components/charts/RadialGauge";

export interface PatientStats {
  vl_history: { result: number; date: string; suppressed: boolean }[];
  treatment_failure_bayesian: {
    posterior_probability: number;
    credible_interval_95: [number, number];
    evidence_readings: number;
    method: string;
  } | null;
  cd4_slope_per_month: number | null;
  cd4_trend: "up" | "down" | "flat";
}

/**
 * Section 8 — StatisticalGauge.
 * Surfaces the backend's Bayesian posterior probability of treatment failure
 * — a genuine Beta-Binomial conjugate update (routers/kpi.py, kpi_engine.py),
 * only computed once 2 consecutive VL readings >= 1000 exist. A Statistical
 * Engineer shows the uncertainty band next to the point estimate, not just
 * the number, so the credible interval is always rendered alongside it.
 */
export function StatisticalGauge({ stats }: { stats: PatientStats }) {
  const TrendIcon = stats.cd4_trend === "up" ? TrendingUp : stats.cd4_trend === "down" ? TrendingDown : Minus;
  const trendColor = stats.cd4_trend === "up" ? "#10B981" : stats.cd4_trend === "down" ? "#EF4444" : "#94A3B8";
  const bayes = stats.treatment_failure_bayesian;

  return (
    <Card>
      <CardHeader><CardTitle>Statistical Analysis</CardTitle></CardHeader>
      <CardContent className="flex items-center gap-6 flex-wrap">
        {bayes ? (
          <div className="flex items-center gap-3">
            <RadialGauge label="Failure Risk" pct={bayes.posterior_probability} color="#EF4444" sublabel="Bayesian posterior" />
            <div className="text-[11px] text-muted-foreground max-w-[220px] flex items-start gap-1.5">
              <AlertTriangle className="h-3.5 w-3.5 text-red-500 flex-shrink-0 mt-0.5" />
              <span>
                2+ consecutive VL readings ≥ 1,000 copies/mL. Posterior computed via a Beta-Binomial conjugate
                update on {bayes.evidence_readings} VL readings.{" "}
                <strong className="text-foreground">95% credible interval: {bayes.credible_interval_95[0]}–{bayes.credible_interval_95[1]}%</strong> —
                treat the point estimate as uncertain within this range, not exact.
              </span>
            </div>
          </div>
        ) : (
          <div className="text-xs text-muted-foreground">
            No consecutive treatment-failure signal — posterior not applicable.
          </div>
        )}

        <div className="flex items-center gap-2 border-l border-border pl-6">
          <TrendIcon className="h-5 w-5" style={{ color: trendColor }} />
          <div>
            <div className="text-xs font-bold text-foreground">
              {stats.cd4_slope_per_month !== null ? `${stats.cd4_slope_per_month > 0 ? "+" : ""}${stats.cd4_slope_per_month} cells/µL / mo` : "Insufficient data"}
            </div>
            <div className="text-[10px] text-muted-foreground uppercase tracking-wide">CD4 6-month slope</div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
