import { AlertTriangle, Clock, Package, CheckCircle, Ban } from "lucide-react";
import type { DsrRow, KanbanStatus } from "@/types";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

/**
 * Section 4C — Kanban Board (Forecast & DSR View)
 *
 * Reasoning: color-coded visual workflow lets a pharmacist triage
 * high-risk inventory lines instantly, without reading raw numbers.
 * Thresholds are computed server-side (routers/forecast.py::days_of_stock_remaining)
 * from ADC over a trailing 90-day window; this component only renders bands.
 *
 * Strict mapping (Section 4C):
 *   CRITICAL  Stock < ADC * 30
 *   LOW       ADC*30  <= Stock < ADC*90
 *   MODERATE  ADC*90  <= Stock < ADC*180
 *   ADEQUATE  Stock >= ADC*180   (eligible for donation, subject to 4B)
 */

const COLUMN_META: Record<
  KanbanStatus,
  { label: string; sub: string; icon: React.ElementType; accent: string; bg: string; border: string }
> = {
  CRITICAL: { label: "Critical", sub: "< 1 month", icon: AlertTriangle, accent: "text-red-700", bg: "bg-red-50", border: "border-red-400" },
  LOW: { label: "Low", sub: "1 – 3 months", icon: Clock, accent: "text-amber-700", bg: "bg-amber-50", border: "border-amber-400" },
  MODERATE: { label: "Moderate", sub: "3 – 6 months", icon: Package, accent: "text-blue-700", bg: "bg-blue-50", border: "border-blue-400" },
  ADEQUATE: { label: "Adequate", sub: "6+ months", icon: CheckCircle, accent: "text-emerald-700", bg: "bg-emerald-50", border: "border-emerald-400" },
};

const COLUMN_ORDER: KanbanStatus[] = ["CRITICAL", "LOW", "MODERATE", "ADEQUATE"];

export function InventoryKanban({
  rows,
  onRequestOrder,
  onOpenNetwork,
}: {
  rows: DsrRow[];
  onRequestOrder?: (row: DsrRow) => void;
  onOpenNetwork?: (row: DsrRow) => void;
}) {
  const grouped: Record<KanbanStatus, DsrRow[]> = { CRITICAL: [], LOW: [], MODERATE: [], ADEQUATE: [] };
  rows.forEach((r) => grouped[r.status]?.push(r));

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
      {COLUMN_ORDER.map((key) => {
        const meta = COLUMN_META[key];
        const Icon = meta.icon;
        const items = grouped[key];
        return (
          <div key={key} className="rounded-xl border border-border bg-muted/40 overflow-hidden min-h-[220px]">
            <div className={cn("px-3 py-2.5 flex items-center gap-2 text-[10px] font-bold uppercase tracking-wide border-b-2", meta.bg, meta.accent, meta.border)}>
              <Icon className="h-3.5 w-3.5" />
              <span>{meta.label}</span>
              <span className="text-[9px] font-medium normal-case text-muted-foreground">{meta.sub}</span>
              <span className="ml-auto rounded-full bg-black/10 px-1.5 py-0.5 text-[10px]">{items.length}</span>
            </div>
            <div className="p-1.5 space-y-1.5">
              {items.length === 0 && (
                <div className="text-center py-6 text-[11px] text-muted-foreground">No drugs in this range</div>
              )}
              {items.map((row) => (
                <DrugKanbanCard key={row.drug_id} row={row} accentBorder={meta.border} onRequestOrder={onRequestOrder} onOpenNetwork={onOpenNetwork} />
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function DrugKanbanCard({
  row, accentBorder, onRequestOrder, onOpenNetwork,
}: { row: DsrRow; accentBorder: string; onRequestOrder?: (row: DsrRow) => void; onOpenNetwork?: (row: DsrRow) => void }) {
  const meta = COLUMN_META[row.status];
  return (
    <div className={cn("rounded-lg bg-white border border-border p-3 border-l-[3px]", accentBorder)}>
      <div className="text-[11px] font-bold text-foreground leading-tight mb-1.5">
        {row.drug_name.split("(")[0].trim()}
      </div>
      <div className={cn("text-2xl font-black leading-none mb-1", meta.accent)}>
        {row.dsr >= 999 ? "∞" : row.dsr}
        <span className="text-xs font-semibold text-muted-foreground"> days</span>
      </div>
      <div className="flex justify-between text-[10px] text-muted-foreground mb-2">
        <span>Stock: <strong className="text-foreground">{row.total_stock}</strong></span>
        <span>ADC: <strong className="text-foreground">{row.adc}</strong>/day</span>
      </div>

      {row.status === "ADEQUATE" ? (
        <DonatableFooter row={row} onOpenNetwork={onOpenNetwork} />
      ) : (
        <Button size="sm" variant="destructive" className="w-full h-7 text-[10px]" onClick={() => onRequestOrder?.(row)}>
          Order {Math.max(0, Math.round(row.adc * 90) - row.total_stock)} units
        </Button>
      )}
    </div>
  );
}

/**
 * Section 4B — Safe-to-Donate footer.
 * Donatable = Current_Stock − (ADC*90 + ADC*30) = Current_Stock − ADC*120.
 * Only rendered/positive on ADEQUATE cards, since DSR >= 180 is required
 * before a facility even has surplus above its own 120-day protected floor.
 */
function DonatableFooter({ row, onOpenNetwork }: { row: DsrRow; onOpenNetwork?: (row: DsrRow) => void }) {
  const donatable = row.donatable_surplus;
  if (donatable <= 0) {
    return (
      <div className="flex items-center gap-1.5 text-[10px] font-semibold text-slate-500 bg-slate-100 rounded px-2 py-1.5 justify-center">
        <Ban className="h-3 w-3" /> Deficit — not donatable
      </div>
    );
  }
  return (
    <Button size="sm" variant="secondary" className="w-full h-7 text-[10px]" onClick={() => onOpenNetwork?.(row)}>
      Donate {donatable} units surplus
    </Button>
  );
}
