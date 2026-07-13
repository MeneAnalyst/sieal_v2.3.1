import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Syringe } from "lucide-react";
import { api } from "@/lib/api";
import { fmtDate } from "@/lib/utils";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import { Table, TableHeader, TableRow, TableHead, TableBody, TableCell } from "@/components/ui/table";

export const Route = createFileRoute("/_authenticated/dispense")({
  component: DispensePage,
});

function DispensePage() {
  const qc = useQueryClient();
  const [clientId, setClientId] = useState("");
  const [drugId, setDrugId] = useState("");
  const [batchId, setBatchId] = useState("");
  const [qty, setQty] = useState("");
  const [toast, setToast] = useState("");

  const { data: patients = [] } = useQuery({ queryKey: ["patients"], queryFn: () => api.patients() });
  const { data: drugs = [] } = useQuery({ queryKey: ["drugs"], queryFn: api.drugs });
  const { data: stock = [] } = useQuery({ queryKey: ["stock"], queryFn: api.stock });
  const { data: recent = [] } = useQuery({ queryKey: ["dispense-recent"], queryFn: () => api.dispenseRecent(20) });

  // FEFO — batches for the selected drug, already earliest-expiry-first
  // because /stock/ is sorted server-side by expiry_date ascending.
  const fefoBatches = stock.filter((b) => String(b.drug_id) === drugId);
  const fefoBatch = fefoBatches[0];

  const dispenseMutation = useMutation({
    mutationFn: () => api.dispense({ client_id: Number(clientId), batch_id: Number(batchId), quantity: Number(qty) }),
    onSuccess: (res) => {
      setToast(`Dispensed ${qty} to ${res.client} — next appointment ${fmtDate(res.next_appointment)}`);
      setClientId(""); setDrugId(""); setBatchId(""); setQty("");
      qc.invalidateQueries({ queryKey: ["dispense-recent"] });
      qc.invalidateQueries({ queryKey: ["stock"] });
      qc.invalidateQueries({ queryKey: ["patients"] });
      setTimeout(() => setToast(""), 5000);
    },
  });

  function onDrugChange(v: string) {
    setDrugId(v);
    const batches = stock.filter((b) => String(b.drug_id) === v);
    setBatchId(batches[0] ? String(batches[0].id) : "");
  }

  return (
    <div className="space-y-4">
      <div>
        <div className="text-lg font-extrabold text-foreground flex items-center gap-2"><Syringe className="h-5 w-5 text-teal-700" /> Dispense</div>
        <div className="text-xs text-muted-foreground mt-0.5">FEFO-enforced medication dispensing</div>
      </div>

      {toast && <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3.5 py-2.5 text-xs text-emerald-800">{toast}</div>}

      <div className="grid grid-cols-1 lg:grid-cols-[360px_1fr] gap-4">
        <Card>
          <CardHeader><CardTitle>New Dispense</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <div>
              <Label className="mb-1.5 block">Recipient *</Label>
              <Select value={clientId} onValueChange={setClientId}>
                <SelectTrigger><SelectValue placeholder="Select patient" /></SelectTrigger>
                <SelectContent>{patients.map((p) => <SelectItem key={p.id} value={String(p.id)}>{p.art_number} · {p.full_name}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div>
              <Label className="mb-1.5 block">Drug *</Label>
              <Select value={drugId} onValueChange={onDrugChange}>
                <SelectTrigger><SelectValue placeholder="Select drug" /></SelectTrigger>
                <SelectContent>{drugs.map((d) => <SelectItem key={d.id} value={String(d.id)}>{d.name}</SelectItem>)}</SelectContent>
              </Select>
            </div>

            {fefoBatch && (
              <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-800">
                <div className="font-bold">FEFO Batch Selected</div>
                <div>Batch {fefoBatch.batch_number} · Exp {fmtDate(fefoBatch.expiry_date)} · {fefoBatch.quantity_remaining} units</div>
              </div>
            )}

            <div>
              <Label className="mb-1.5 block">Batch</Label>
              <Select value={batchId} onValueChange={setBatchId} disabled={!drugId}>
                <SelectTrigger><SelectValue placeholder={drugId ? "Select batch" : "Select drug first"} /></SelectTrigger>
                <SelectContent>
                  {fefoBatches.map((b) => (
                    <SelectItem key={b.id} value={String(b.id)}>
                      [{b.alert_status}] {b.batch_number} — Exp:{fmtDate(b.expiry_date)} — {b.quantity_remaining}u
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div>
              <Label className="mb-1.5 block">Quantity</Label>
              <Input type="number" value={qty} onChange={(e) => setQty(e.target.value)} placeholder="e.g. 60" />
            </div>

            <Button
              className="w-full"
              disabled={!clientId || !batchId || !qty || dispenseMutation.isPending}
              onClick={() => dispenseMutation.mutate()}
            >
              {dispenseMutation.isPending ? "Dispensing..." : "Confirm Dispense"}
            </Button>
            {dispenseMutation.isError && (
              <div className="text-xs text-red-600">{dispenseMutation.error instanceof Error ? dispenseMutation.error.message : "Failed"}</div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>Recent Dispenses</CardTitle></CardHeader>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow><TableHead>Client</TableHead><TableHead>ART No.</TableHead><TableHead>Drug</TableHead><TableHead>Qty</TableHead><TableHead>Date</TableHead></TableRow>
              </TableHeader>
              <TableBody>
                {recent.map((r) => (
                  <TableRow key={r.id}>
                    <TableCell className="font-semibold text-foreground">{r.client_name}</TableCell>
                    <TableCell className="mono">{r.art_number}</TableCell>
                    <TableCell>{r.drug_name.split("(")[0].trim().substring(0, 22)}</TableCell>
                    <TableCell className="font-bold">{r.quantity}</TableCell>
                    <TableCell>{fmtDate(r.dispense_date)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
