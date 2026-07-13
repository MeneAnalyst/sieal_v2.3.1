import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { InventoryKanban } from "@/components/forecast/InventoryKanban";
import type { DsrRow } from "@/types";

export const Route = createFileRoute("/_authenticated/forecast")({
  component: ForecastPage,
});

function ForecastPage() {
  const navigate = useNavigate();
  const { data: dsr = [], isLoading } = useQuery({ queryKey: ["dsr"], queryFn: api.dsr });

  function handleOpenNetwork(row: DsrRow) {
    navigate({ to: "/network", search: { drug_id: row.drug_id } as never });
  }

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between">
        <div>
          <div className="text-lg font-extrabold text-foreground">Forecast &amp; Kanban</div>
          <div className="text-xs text-muted-foreground mt-0.5">
            Inventory workflow by Days of Stock Remaining — ADC computed over a trailing 90-day window.
          </div>
        </div>
      </div>

      {isLoading ? (
        <div className="text-center py-16 text-muted-foreground text-sm">Loading forecast...</div>
      ) : (
        <InventoryKanban
          rows={dsr}
          onRequestOrder={(row) => navigate({ to: "/network", search: { drug_id: row.drug_id } as never })}
          onOpenNetwork={handleOpenNetwork}
        />
      )}

      <div className="rounded-lg border border-border bg-muted/40 p-3 text-[11px] text-muted-foreground leading-relaxed">
        <strong className="text-foreground">Reasoning:</strong> Critical &lt; 30 days, Low 30–90, Moderate 90–180,
        Adequate ≥ 180 days of stock. A drug only becomes donation-eligible once it clears the 120-day protected
        floor (90-day order cycle + 30-day emergency buffer) — see Stock Network for Safe-to-Donate calculations.
      </div>
    </div>
  );
}
