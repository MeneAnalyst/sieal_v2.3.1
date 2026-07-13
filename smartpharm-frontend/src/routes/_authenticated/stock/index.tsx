import { createFileRoute } from "@tanstack/react-router";
import { useState, useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, QrCode, PackagePlus, Pill, Ban, Pencil, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { fmtDate } from "@/lib/utils";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import { Table, TableHeader, TableRow, TableHead, TableBody, TableCell } from "@/components/ui/table";
import { SortableTh, sortRows, type SortDir } from "@/components/ui/sortable-th";
import { ScanStockDialog } from "@/components/stock/QrScanner";
import type { Batch } from "@/types";

export const Route = createFileRoute("/_authenticated/stock/")({
  component: StockPage,
});

const RAG_VARIANT = { RED: "red", AMBER: "amber", GREEN: "green" } as const;

function StockPage() {
  const [scanOpen, setScanOpen] = useState(false);
  const [receiveOpen, setReceiveOpen] = useState(false);
  const [lossBatch, setLossBatch] = useState<Batch | null>(null);
  const [drugModalOpen, setDrugModalOpen] = useState(false);
  const [editBatch, setEditBatch] = useState<Batch | null>(null);
  const [deleteBatch, setDeleteBatch] = useState<Batch | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [sortKey, setSortKey] = useState<keyof Batch | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>(null);

  function handleSort(key: string) {
    if (sortKey !== key) { setSortKey(key as keyof Batch); setSortDir("asc"); }
    else if (sortDir === "asc") setSortDir("desc");
    else if (sortDir === "desc") { setSortKey(null); setSortDir(null); }
    else setSortDir("asc");
  }

  // Section 4A — backend /stock/ already returns batches ordered by
  // expiry_date ascending (FEFO). We render in that order verbatim.
  const { data: stock = [], isLoading } = useQuery({ queryKey: ["stock"], queryFn: api.stock });
  const { data: alerts = [] } = useQuery({ queryKey: ["stock-alerts"], queryFn: api.stockAlerts });

  const red = alerts.filter((a) => a.alert_status === "RED");

  const filteredStock = stock.filter((b) => {
    const matchesSearch = !search || b.drug_name.toLowerCase().includes(search.toLowerCase()) || b.batch_number.toLowerCase().includes(search.toLowerCase());
    const matchesStatus = statusFilter === "ALL" || b.alert_status === statusFilter;
    return matchesSearch && matchesStatus;
  });
  const sortedStock = sortRows(filteredStock, sortKey, sortDir);

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <div className="text-lg font-extrabold text-foreground">Stock Register</div>
          <div className="text-xs text-muted-foreground mt-0.5">
            {filteredStock.length} of {stock.length} batches shown — FEFO order (earliest expiry first)
          </div>
        </div>
        <div className="flex gap-2 flex-wrap items-center">
          <Input placeholder="Search drug or batch number..." value={search} onChange={(e) => setSearch(e.target.value)} className="w-56" />
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className="w-32"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="ALL">All statuses</SelectItem>
              <SelectItem value="RED">RED</SelectItem>
              <SelectItem value="AMBER">AMBER</SelectItem>
              <SelectItem value="GREEN">GREEN</SelectItem>
            </SelectContent>
          </Select>
          <Button variant="outline" size="sm" className="gap-1.5" onClick={() => setDrugModalOpen(true)}>
            <Pill className="h-3.5 w-3.5" /> Drug
          </Button>
          <Button variant="secondary" size="sm" className="gap-1.5" onClick={() => setScanOpen(true)}>
            <QrCode className="h-3.5 w-3.5" /> Scan QR
          </Button>
          <Button size="sm" className="gap-1.5" onClick={() => setReceiveOpen(true)}>
            <PackagePlus className="h-3.5 w-3.5" /> Manual Receive
          </Button>
        </div>
      </div>

      {red.length > 0 && (
        <div className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 px-3.5 py-2.5 text-xs text-red-800">
          <AlertTriangle className="h-4 w-4 flex-shrink-0 mt-0.5" />
          <div>
            <strong>{red.length} batch{red.length > 1 ? "es" : ""} expiring within 30 days:</strong>{" "}
            {red.map((b) => b.drug_name.split("(")[0].trim()).join(", ")}
          </div>
        </div>
      )}

      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <SortableTh label="Drug" sortKey="drug_name" activeKey={sortKey} dir={sortDir} onSort={handleSort} />
                <SortableTh label="Batch" sortKey="batch_number" activeKey={sortKey} dir={sortDir} onSort={handleSort} />
                <SortableTh label="Expiry" sortKey="expiry_date" activeKey={sortKey} dir={sortDir} onSort={handleSort} />
                <SortableTh label="Days Left" sortKey="days_to_expiry" activeKey={sortKey} dir={sortDir} onSort={handleSort} />
                <SortableTh label="Remaining" sortKey="quantity_remaining" activeKey={sortKey} dir={sortDir} onSort={handleSort} />
                <TableHead>Source</TableHead>
                <SortableTh label="Status" sortKey="alert_status" activeKey={sortKey} dir={sortDir} onSort={handleSort} />
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading && <TableRow><TableCell colSpan={8} className="text-center py-10 text-muted-foreground">Loading...</TableCell></TableRow>}
              {!isLoading && stock.length === 0 && (
                <TableRow><TableCell colSpan={8} className="text-center py-10 text-muted-foreground">No stock recorded. Receive a delivery to get started.</TableCell></TableRow>
              )}
              {!isLoading && stock.length > 0 && filteredStock.length === 0 && (
                <TableRow><TableCell colSpan={8} className="text-center py-10 text-muted-foreground">No batches match this search/filter.</TableCell></TableRow>
              )}
              {filteredStock.length > 0 && sortedStock.map((b) => (
                <TableRow key={b.id}>
                  <TableCell>
                    <div className="font-semibold text-foreground">{b.drug_name}</div>
                    <div className="text-[10px] text-muted-foreground">{b.drug_strength}</div>
                  </TableCell>
                  <TableCell className="mono">{b.batch_number}</TableCell>
                  <TableCell>{fmtDate(b.expiry_date)}</TableCell>
                  <TableCell className="font-bold" style={{ color: b.days_to_expiry <= 30 ? "#EF4444" : b.days_to_expiry <= 90 ? "#F59E0B" : "#10B981" }}>
                    {b.days_to_expiry}d
                  </TableCell>
                  <TableCell>
                    <span className="font-bold">{b.quantity_remaining}</span>
                    <span className="text-muted-foreground text-[10px]"> /{b.quantity_received}</span>
                  </TableCell>
                  <TableCell>{b.scan_logged ? <Badge variant="blue">QR Scan</Badge> : <Badge variant="gray">Manual</Badge>}</TableCell>
                  <TableCell><Badge variant={RAG_VARIANT[b.alert_status]}>{b.alert_status}</Badge></TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-1">
                      <Button size="sm" variant="outline" className="h-6 text-[10px] gap-1" onClick={() => setLossBatch(b)}>
                        <Ban className="h-3 w-3" /> Loss
                      </Button>
                      <Button size="sm" variant="outline" className="h-6 w-6 p-0" title="Edit batch" onClick={() => setEditBatch(b)}>
                        <Pencil className="h-3 w-3" />
                      </Button>
                      <Button size="sm" variant="outline" className="h-6 w-6 p-0 text-red-600 hover:bg-red-50 hover:text-red-700" title="Delete batch" onClick={() => setDeleteBatch(b)}>
                        <Trash2 className="h-3 w-3" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <ScanStockDialog open={scanOpen} onOpenChange={setScanOpen} />
      <ManualReceiveDialog open={receiveOpen} onOpenChange={setReceiveOpen} />
      <AddDrugDialog open={drugModalOpen} onOpenChange={setDrugModalOpen} />
      <ExpiryLossDialog batch={lossBatch} onOpenChange={(v) => !v && setLossBatch(null)} />
      <EditBatchDialog batch={editBatch} onOpenChange={(v) => !v && setEditBatch(null)} />
      <DeleteBatchDialog batch={deleteBatch} onOpenChange={(v) => !v && setDeleteBatch(null)} />
    </div>
  );
}

function ManualReceiveDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  const qc = useQueryClient();
  const [drugId, setDrugId] = useState("");
  const [batch, setBatch] = useState("");
  const [expiry, setExpiry] = useState("");
  const [qty, setQty] = useState("");
  const [supplier, setSupplier] = useState("NatPharm Zimbabwe");
  const { data: drugs = [] } = useQuery({ queryKey: ["drugs"], queryFn: api.drugs, enabled: open });

  const mutation = useMutation({
    mutationFn: () => api.receiveStock({ drug_id: Number(drugId), batch_number: batch, expiry_date: expiry, quantity_received: Number(qty), supplier }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["stock"] });
      qc.invalidateQueries({ queryKey: ["dsr"] });
      setDrugId(""); setBatch(""); setExpiry(""); setQty("");
      onOpenChange(false);
    },
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader><DialogTitle>Receive Stock</DialogTitle></DialogHeader>
        <div>
          <Label className="mb-1.5 block">Drug *</Label>
          <Select value={drugId} onValueChange={setDrugId}>
            <SelectTrigger><SelectValue placeholder="Select drug" /></SelectTrigger>
            <SelectContent>{drugs.map((d) => <SelectItem key={d.id} value={String(d.id)}>{d.name}</SelectItem>)}</SelectContent>
          </Select>
        </div>
        <div className="grid grid-cols-2 gap-2.5">
          <div><Label className="mb-1.5 block">Batch *</Label><Input value={batch} onChange={(e) => setBatch(e.target.value)} placeholder="TLD-ZW-2025-001" /></div>
          <div><Label className="mb-1.5 block">Expiry *</Label><Input type="date" value={expiry} onChange={(e) => setExpiry(e.target.value)} /></div>
          <div><Label className="mb-1.5 block">Qty *</Label><Input type="number" value={qty} onChange={(e) => setQty(e.target.value)} /></div>
          <div><Label className="mb-1.5 block">Supplier</Label><Input value={supplier} onChange={(e) => setSupplier(e.target.value)} /></div>
        </div>
        <Button className="w-full" disabled={!drugId || !batch || !expiry || !qty || mutation.isPending} onClick={() => mutation.mutate()}>
          {mutation.isPending ? "Confirming..." : "Confirm Receipt"}
        </Button>
      </DialogContent>
    </Dialog>
  );
}

function AddDrugDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [strength, setStrength] = useState("");
  const [form, setForm] = useState("Tablet");
  const [category, setCategory] = useState("ART");

  const mutation = useMutation({
    mutationFn: () => api.createDrug({ name, strength, form, category }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["drugs"] });
      setName(""); setStrength("");
      onOpenChange(false);
    },
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader><DialogTitle>Add Drug to Registry</DialogTitle></DialogHeader>
        <div><Label className="mb-1.5 block">Drug Name *</Label><Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Tenofovir/Lamivudine/Dolutegravir" /></div>
        <div className="grid grid-cols-2 gap-2.5">
          <div><Label className="mb-1.5 block">Strength</Label><Input value={strength} onChange={(e) => setStrength(e.target.value)} placeholder="300/300/50mg" /></div>
          <div>
            <Label className="mb-1.5 block">Form</Label>
            <Select value={form} onValueChange={setForm}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>{["Tablet", "Capsule", "Syrup", "Injection"].map((f) => <SelectItem key={f} value={f}>{f}</SelectItem>)}</SelectContent>
            </Select>
          </div>
        </div>
        <div>
          <Label className="mb-1.5 block">Category</Label>
          <Select value={category} onValueChange={setCategory}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>{["ART", "Prophylaxis", "OI Treatment", "Other"].map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}</SelectContent>
          </Select>
        </div>
        <Button className="w-full" disabled={!name || mutation.isPending} onClick={() => mutation.mutate()}>
          {mutation.isPending ? "Adding..." : "Add Drug"}
        </Button>
      </DialogContent>
    </Dialog>
  );
}

function ExpiryLossDialog({ batch, onOpenChange }: { batch: Batch | null; onOpenChange: (v: boolean) => void }) {
  const qc = useQueryClient();
  const [qty, setQty] = useState("");
  const [reason, setReason] = useState("DEMAND_SHORTFALL");
  const [notes, setNotes] = useState("");

  const mutation = useMutation({
    mutationFn: () => api.recordLoss({ batch_id: batch!.id, quantity_lost: Number(qty), reason_code: reason, notes: notes || null }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["stock"] });
      setQty(""); setNotes("");
      onOpenChange(false);
    },
  });

  return (
    <Dialog open={!!batch} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader><DialogTitle>Record Expiry Loss</DialogTitle></DialogHeader>
        {batch && (
          <>
            <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-800">
              {batch.drug_name} — {batch.quantity_remaining} units remaining
            </div>
            <div><Label className="mb-1.5 block">Quantity Lost</Label><Input type="number" max={batch.quantity_remaining} value={qty} onChange={(e) => setQty(e.target.value)} /></div>
            <div>
              <Label className="mb-1.5 block">Reason</Label>
              <Select value={reason} onValueChange={setReason}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {["DEMAND_SHORTFALL", "FORECAST_ERROR", "DELIVERY_EXCESS", "OTHER"].map((r) => (
                    <SelectItem key={r} value={r}>{r.replace(/_/g, " ")}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div><Label className="mb-1.5 block">Notes</Label><Input value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Optional" /></div>
            <Button variant="destructive" className="w-full" disabled={!qty || mutation.isPending} onClick={() => mutation.mutate()}>
              {mutation.isPending ? "Confirming..." : "Confirm Write-Off"}
            </Button>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

function EditBatchDialog({ batch, onOpenChange }: { batch: Batch | null; onOpenChange: (v: boolean) => void }) {
  const qc = useQueryClient();
  const [batchNumber, setBatchNumber] = useState("");
  const [expiry, setExpiry] = useState("");
  const [supplier, setSupplier] = useState("");
  const [gtin, setGtin] = useState("");

  // Re-sync whenever a different batch is opened for editing.
  useEffect(() => {
    if (batch) {
      setBatchNumber(batch.batch_number);
      setExpiry(batch.expiry_date);
      setSupplier("");
      setGtin("");
    }
  }, [batch?.id]);

  const mutation = useMutation({
    mutationFn: () =>
      api.updateBatch(batch!.id, {
        batch_number: batchNumber, expiry_date: expiry,
        ...(supplier ? { supplier } : {}), ...(gtin ? { gtin } : {}),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["stock"] });
      onOpenChange(false);
    },
  });

  return (
    <Dialog open={!!batch} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader><DialogTitle>Edit Batch Details</DialogTitle></DialogHeader>
        {batch && (
          <>
            <div className="rounded-lg border border-teal-200 bg-teal-50 px-3 py-2 text-xs text-teal-800">
              {batch.drug_name} — {batch.quantity_remaining} units remaining (quantities aren't editable here —
              use Receive Stock or Record Loss for that)
            </div>
            <div className="grid grid-cols-2 gap-2.5">
              <div><Label className="mb-1.5 block">Batch Number</Label><Input value={batchNumber} onChange={(e) => setBatchNumber(e.target.value)} /></div>
              <div><Label className="mb-1.5 block">Expiry Date</Label><Input type="date" value={expiry} onChange={(e) => setExpiry(e.target.value)} /></div>
              <div><Label className="mb-1.5 block">Supplier</Label><Input value={supplier} onChange={(e) => setSupplier(e.target.value)} placeholder={batch.drug_name ? "NatPharm Zimbabwe" : ""} /></div>
              <div><Label className="mb-1.5 block">GTIN</Label><Input value={gtin} onChange={(e) => setGtin(e.target.value)} placeholder="Optional" /></div>
            </div>
            {mutation.isError && <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-800">{mutation.error.message}</div>}
            <Button className="w-full" disabled={!batchNumber || !expiry || mutation.isPending} onClick={() => mutation.mutate()}>
              {mutation.isPending ? "Saving..." : "Save Changes"}
            </Button>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

function DeleteBatchDialog({ batch, onOpenChange }: { batch: Batch | null; onOpenChange: (v: boolean) => void }) {
  const qc = useQueryClient();
  const mutation = useMutation({
    mutationFn: () => api.deleteBatch(batch!.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["stock"] });
      onOpenChange(false);
    },
  });

  return (
    <Dialog open={!!batch} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader><DialogTitle>Delete Batch</DialogTitle></DialogHeader>
        {batch && (
          <>
            <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
              Delete <strong>{batch.batch_number}</strong> ({batch.drug_name})? This only works if the batch has
              never been dispensed from or had a loss recorded against it — otherwise the server will reject
              this to protect the audit trail, and you'll see why below.
            </div>
            {mutation.isError && <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-800">{mutation.error.message}</div>}
            <Button variant="destructive" className="w-full" disabled={mutation.isPending} onClick={() => mutation.mutate()}>
              {mutation.isPending ? "Deleting..." : "Delete Batch"}
            </Button>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
