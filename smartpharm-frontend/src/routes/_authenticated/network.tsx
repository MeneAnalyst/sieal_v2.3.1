import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Ban, CheckCircle2, Network as NetworkIcon, Building2, Clock, ClipboardCheck, ReceiptText } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from "@/components/ui/select";
import type { DonorRecommendation } from "@/types";

export const Route = createFileRoute("/_authenticated/network")({
  component: NetworkPage,
});

function NetworkPage() {
  const qc = useQueryClient();
  const [drugId, setDrugId] = useState<string>("");
  const [qty, setQty] = useState<string>("");
  const [searchedFor, setSearchedFor] = useState<{ drugId: number; qty: number } | null>(null);

  const { data: drugs = [] } = useQuery({ queryKey: ["drugs"], queryFn: api.drugs });
  const { data: summary } = useQuery({ queryKey: ["network-summary"], queryFn: api.networkSummary });
  const { data: facilities = [] } = useQuery({ queryKey: ["network-facilities"], queryFn: api.networkFacilities });

  const { data: finderResult, isFetching: finding } = useQuery({
    queryKey: ["can-share", searchedFor?.drugId, searchedFor?.qty],
    queryFn: () => api.canShare(searchedFor!.drugId, searchedFor!.qty),
    enabled: !!searchedFor,
  });

  const requestMutation = useMutation({
    mutationFn: (payload: { drug_id: number; donor_facility_id: number; receiver_facility_id: number; quantity_requested: number }) =>
      api.requestTransfer(payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["network-summary"] }),
  });

  const me = facilities.find((f) => f.is_current);

  function runFinder() {
    if (!drugId || !qty) return;
    setSearchedFor({ drugId: Number(drugId), qty: Number(qty) });
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <NetworkIcon className="h-5 w-5 text-teal-700" />
        <div>
          <div className="text-lg font-extrabold text-foreground">Stock Sharing Network</div>
          <div className="text-xs text-muted-foreground">
            {facilities.length} facilities · {summary?.total_facilities ?? 0} registered · Safe-to-Donate = Stock − (ADC × 120)
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <StatCard label="Facilities" value={summary?.total_facilities ?? 0} color="#0D9488" icon={Building2} />
        <StatCard label="Active Requests" value={summary?.active_requests ?? 0} color="#F59E0B" icon={Clock} />
        <StatCard label="Completed" value={summary?.completed_transfers ?? 0} color="#10B981" icon={ClipboardCheck} />
        <StatCard label="Repayments Due" value={summary?.outstanding_obligations ?? 0} color="#EF4444" icon={ReceiptText} />
      </div>

      <Card>
        <CardHeader><CardTitle>Smart Stock Finder — Who Can Help?</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-[1fr_1fr_auto] gap-2.5 items-end">
            <div>
              <Label className="mb-1.5 block">Drug Needed</Label>
              <Select value={drugId} onValueChange={setDrugId}>
                <SelectTrigger><SelectValue placeholder="Select drug" /></SelectTrigger>
                <SelectContent>{drugs.map((d) => <SelectItem key={d.id} value={String(d.id)}>{d.name}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div>
              <Label className="mb-1.5 block">Quantity</Label>
              <Input type="number" value={qty} onChange={(e) => setQty(e.target.value)} placeholder="e.g. 200" />
            </div>
            <Button onClick={runFinder} disabled={!drugId || !qty}>Find Donors</Button>
          </div>

          {finding && <div className="text-xs text-muted-foreground">Analysing network surplus...</div>}

          {finderResult && (
            <div className="space-y-3">
              {finderResult.recommendations.length === 0 ? (
                <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                  No facility has safe surplus of <strong>{finderResult.drug_name}</strong>. Contact NatPharm directly.
                </div>
              ) : (
                <>
                  <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-800">
                    Found <strong>{finderResult.recommendations.length}</strong> donor(s) — combined{" "}
                    <strong>{finderResult.combined_available}</strong> units safely available.
                  </div>
                  <div className="rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-[11px] text-blue-800">
                    {finderResult.data_note}
                  </div>
                  <div className="space-y-2">
                    {finderResult.recommendations.map((rec, i) => (
                      <DonorRow
                        key={rec.facility_id}
                        rec={rec}
                        rank={i + 1}
                        onRequest={() =>
                          me &&
                          requestMutation.mutate({
                            drug_id: Number(drugId),
                            donor_facility_id: rec.facility_id,
                            receiver_facility_id: me.id,
                            quantity_requested: rec.recommended_qty,
                          })
                        }
                      />
                    ))}
                  </div>
                </>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function DonorRow({ rec, rank, onRequest }: { rec: DonorRecommendation; rank: number; onRequest: () => void }) {
  // Section 4B / Section 8 checklist item 5: the Request/Donate action is
  // strictly disabled unless the donor's safe_to_donate > 0 — this mirrors
  // the backend's own validation so a donor can never be incapacitated.
  const canDonate = rec.safe_to_donate > 0;
  return (
    <div className={`flex items-center gap-3 rounded-lg border p-3 ${rank === 1 ? "bg-emerald-50/60 border-emerald-200" : "border-border"}`}>
      <div className={`text-lg font-black w-7 text-center ${rank === 1 ? "text-emerald-600" : "text-slate-300"}`}>#{rank}</div>
      <div className="flex-1 min-w-0">
        <div className="font-semibold text-sm text-foreground truncate">{rec.facility_name}</div>
        <div className="flex items-center gap-2 mt-0.5">
          {rec.can_cover_full ? <Badge variant="green">Full Coverage</Badge> : <Badge variant="amber">Partial</Badge>}
          <span className="text-[11px] text-muted-foreground">DSR after: {rec.dsr_after}d</span>
          {rec.distance_km !== null && <span className="text-[11px] text-muted-foreground">{rec.distance_km}km away</span>}
        </div>
      </div>
      <div className="text-right">
        <div className="text-xs text-muted-foreground">Safe to donate</div>
        <div className="font-bold text-emerald-700">{rec.safe_to_donate}</div>
      </div>
      <Button size="sm" disabled={!canDonate} onClick={onRequest} className="gap-1">
        {canDonate ? <><CheckCircle2 className="h-3.5 w-3.5" /> Request {rec.recommended_qty}</> : <><Ban className="h-3.5 w-3.5" /> Deficit</>}
      </Button>
    </div>
  );
}

function StatCard({ label, value, color, icon: Icon, to }: { label: string; value: number; color: string; icon: LucideIcon; to?: string }) {
  const navigate = useNavigate();
  return (
    <Card
      role={to ? "button" : undefined}
      tabIndex={to ? 0 : undefined}
      onClick={to ? () => navigate({ to }) : undefined}
      onKeyDown={to ? (e) => { if (e.key === "Enter") navigate({ to }); } : undefined}
      className={cn("p-4 transition-all", to && "cursor-pointer hover:-translate-y-0.5 hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring")}
    >
      <div className="flex items-center justify-between mb-1">
        <div className="text-[10px] font-bold uppercase tracking-wide text-muted-foreground">{label}</div>
        <div className="w-6 h-6 rounded-md flex items-center justify-center flex-shrink-0" style={{ background: `${color}18` }}>
          <Icon className="h-3.5 w-3.5" style={{ color }} />
        </div>
      </div>
      <div className="text-2xl font-black" style={{ color }}>{value}</div>
    </Card>
  );
}
