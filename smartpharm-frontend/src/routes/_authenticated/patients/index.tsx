import { createFileRoute, Link } from "@tanstack/react-router";
import { useState, useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Pencil, Trash2 } from "lucide-react";
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
import type { Patient } from "@/types";

export const Route = createFileRoute("/_authenticated/patients/")({
  component: PatientsPage,
});

const STATUS_VARIANT: Record<string, "green" | "red" | "amber" | "blue" | "gray"> = {
  ACTIVE: "green", LTFU: "red", RTT: "amber", NEW_INITIATION: "blue", TREATMENT_FAILURE: "red",
};

const TREATMENT_COMBOS = [
  "TDF + 3TC + DTG (TLD)", "TDF + 3TC + EFV", "AZT + NVP", "AZT + NVP + 3TC",
  "TDF + 3TC + NVP", "AZT + NVP + 3TC + EFV", "ABC", "2nd Line", "3HP", "INH", "TLE600",
];
const PROGRESS_STATUSES = ["ACTIVE", "LTFU", "RTT", "TREATMENT_FAILURE", "NEW_INITIATION", "TRANSFERRED_OUT"];

function PatientsPage() {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [sortKey, setSortKey] = useState<keyof Patient | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>(null);

  function handleSort(key: string) {
    if (sortKey !== key) { setSortKey(key as keyof Patient); setSortDir("asc"); }
    else if (sortDir === "asc") setSortDir("desc");
    else if (sortDir === "desc") { setSortKey(null); setSortDir(null); }
    else setSortDir("asc");
  }
  const [addOpen, setAddOpen] = useState(false);
  const [editPatient, setEditPatient] = useState<Patient | null>(null);
  const [deletePatient, setDeletePatient] = useState<Patient | null>(null);
  const { data: patients = [], isLoading } = useQuery({ queryKey: ["patients"], queryFn: () => api.patients() });

  const filtered = patients.filter((p) => {
    const matchesSearch = !search || p.full_name.toLowerCase().includes(search.toLowerCase()) || p.art_number.toLowerCase().includes(search.toLowerCase());
    const matchesStatus = statusFilter === "ALL" || p.progress_status === statusFilter;
    return matchesSearch && matchesStatus;
  });
  const sorted = sortRows(filtered, sortKey, sortDir);

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <div className="text-lg font-extrabold text-foreground">Recipients of Care</div>
          <div className="text-xs text-muted-foreground mt-0.5">{filtered.length} of {patients.length} patients shown</div>
        </div>
        <div className="flex gap-2 items-center flex-wrap">
          <Input placeholder="Search name or ART number..." value={search} onChange={(e) => setSearch(e.target.value)} className="w-56" />
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className="w-40"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="ALL">All statuses</SelectItem>
              {PROGRESS_STATUSES.map((s) => <SelectItem key={s} value={s}>{s.replace(/_/g, " ")}</SelectItem>)}
            </SelectContent>
          </Select>
          <Button size="sm" className="gap-1.5" onClick={() => setAddOpen(true)}>
            <Plus className="h-3.5 w-3.5" /> Add Patient
          </Button>
        </div>
      </div>

      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <SortableTh label="ART Number" sortKey="art_number" activeKey={sortKey} dir={sortDir} onSort={handleSort} />
                <SortableTh label="Name" sortKey="full_name" activeKey={sortKey} dir={sortDir} onSort={handleSort} />
                <SortableTh label="CD4" sortKey="cd4_count" activeKey={sortKey} dir={sortDir} onSort={handleSort} />
                <SortableTh label="VL" sortKey="vl_result" activeKey={sortKey} dir={sortDir} onSort={handleSort} />
                <SortableTh label="Status" sortKey="progress_status" activeKey={sortKey} dir={sortDir} onSort={handleSort} />
                <SortableTh label="Next Appt" sortKey="next_appointment" activeKey={sortKey} dir={sortDir} onSort={handleSort} />
                <TableHead>ECI</TableHead><TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading && <TableRow><TableCell colSpan={8} className="text-center py-10 text-muted-foreground">Loading...</TableCell></TableRow>}
              {!isLoading && filtered.length === 0 && (
                <TableRow><TableCell colSpan={8} className="text-center py-10 text-muted-foreground">No patients found</TableCell></TableRow>
              )}
              {filtered.length > 0 && sorted.map((p) => (
                <TableRow key={p.id}>
                  <TableCell className="mono">
                    <Link to="/patients/$patientId" params={{ patientId: String(p.id) }} className="text-teal-700 hover:underline font-semibold">
                      {p.art_number}
                    </Link>
                  </TableCell>
                  <TableCell className="font-semibold text-foreground">{p.full_name}</TableCell>
                  <TableCell className="font-bold" style={{ color: p.cd4_count && p.cd4_count < 200 ? "#EF4444" : undefined }}>
                    {p.cd4_count ?? "—"}
                  </TableCell>
                  <TableCell className="font-bold" style={{ color: p.vl_result && !p.vl_suppressed ? "#EF4444" : "#10B981" }}>
                    {p.vl_result?.toLocaleString() ?? "—"}
                  </TableCell>
                  <TableCell><Badge variant={STATUS_VARIANT[p.progress_status] ?? "gray"}>{p.progress_status.replace(/_/g, " ")}</Badge></TableCell>
                  <TableCell>{fmtDate(p.next_appointment)}</TableCell>
                  <TableCell>{p.is_eci_flag ? <Badge variant="red">ECI</Badge> : "—"}</TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-1">
                      <Button size="sm" variant="outline" className="h-7 w-7 p-0" title="Edit patient" onClick={() => setEditPatient(p)}>
                        <Pencil className="h-3.5 w-3.5" />
                      </Button>
                      <Button size="sm" variant="outline" className="h-7 w-7 p-0 text-red-600 hover:bg-red-50 hover:text-red-700" title="Deactivate patient" onClick={() => setDeletePatient(p)}>
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <AddPatientDialog open={addOpen} onOpenChange={setAddOpen} />
      <EditPatientDialog patient={editPatient} onOpenChange={(v) => !v && setEditPatient(null)} />
      <DeactivatePatientDialog patient={deletePatient} onOpenChange={(v) => !v && setDeletePatient(null)} />
    </div>
  );
}

function AddPatientDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  const qc = useQueryClient();
  const [artNumber, setArtNumber] = useState("");
  const [fullName, setFullName] = useState("");
  const [gender, setGender] = useState("");
  const [dob, setDob] = useState("");
  const [combo, setCombo] = useState("");
  const [visitType, setVisitType] = useState("PHARMACY");
  const [enrollmentDate, setEnrollmentDate] = useState(new Date().toISOString().split("T")[0]);

  const mutation = useMutation({
    mutationFn: () =>
      api.createPatient({
        art_number: artNumber, full_name: fullName, gender: gender || null,
        date_of_birth: dob || null, treatment_combination: combo, regime: combo,
        visit_type: visitType, enrollment_date: enrollmentDate,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["patients"] });
      setArtNumber(""); setFullName(""); setGender(""); setDob(""); setCombo("");
      onOpenChange(false);
    },
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader><DialogTitle>Register Recipient of Care</DialogTitle></DialogHeader>
        <div className="grid grid-cols-2 gap-2.5">
          <div><Label className="mb-1.5 block">ART Number *</Label><Input value={artNumber} onChange={(e) => setArtNumber(e.target.value)} placeholder="09-0A-06-2026-A-00001" /></div>
          <div><Label className="mb-1.5 block">Full Name *</Label><Input value={fullName} onChange={(e) => setFullName(e.target.value)} /></div>
          <div><Label className="mb-1.5 block">Date of Birth</Label><Input type="date" value={dob} onChange={(e) => setDob(e.target.value)} /></div>
          <div>
            <Label className="mb-1.5 block">Gender</Label>
            <Select value={gender} onValueChange={setGender}>
              <SelectTrigger><SelectValue placeholder="—" /></SelectTrigger>
              <SelectContent><SelectItem value="F">F</SelectItem><SelectItem value="M">M</SelectItem></SelectContent>
            </Select>
          </div>
        </div>
        <div>
          <Label className="mb-1.5 block">Treatment Combination *</Label>
          <Select value={combo} onValueChange={setCombo}>
            <SelectTrigger><SelectValue placeholder="Select combination" /></SelectTrigger>
            <SelectContent>{TREATMENT_COMBOS.map((t) => <SelectItem key={t} value={t}>{t}</SelectItem>)}</SelectContent>
          </Select>
        </div>
        <div className="grid grid-cols-2 gap-2.5">
          <div>
            <Label className="mb-1.5 block">Visit Type</Label>
            <Select value={visitType} onValueChange={setVisitType}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="PHARMACY">Pharmacy (6 months)</SelectItem>
                <SelectItem value="CLINICAL">Clinical (3 months)</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div><Label className="mb-1.5 block">Enrollment Date *</Label><Input type="date" value={enrollmentDate} onChange={(e) => setEnrollmentDate(e.target.value)} /></div>
        </div>
        {mutation.isError && <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-800">{mutation.error.message}</div>}
        <Button className="w-full" disabled={!artNumber || !fullName || !combo || !enrollmentDate || mutation.isPending} onClick={() => mutation.mutate()}>
          {mutation.isPending ? "Registering..." : "Register Patient"}
        </Button>
      </DialogContent>
    </Dialog>
  );
}

function EditPatientDialog({ patient, onOpenChange }: { patient: Patient | null; onOpenChange: (v: boolean) => void }) {
  const qc = useQueryClient();
  const [fullName, setFullName] = useState("");
  const [combo, setCombo] = useState("");
  const [status, setStatus] = useState("");
  const [cd4, setCd4] = useState("");

  // Re-sync form fields whenever a different patient is opened for
  // editing (or the dialog re-opens for the same one after a previous
  // close). Keyed on patient?.id so it fires exactly once per patient,
  // not on every render.
  useEffect(() => {
    if (patient) {
      setFullName(patient.full_name);
      setCombo(patient.treatment_combination ?? "");
      setStatus(patient.progress_status);
      setCd4(patient.cd4_count?.toString() ?? "");
    }
  }, [patient?.id]);

  const mutation = useMutation({
    mutationFn: () =>
      api.updatePatient(patient!.id, {
        full_name: fullName, treatment_combination: combo, regime: combo,
        progress_status: status, cd4_count: cd4 ? Number(cd4) : null,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["patients"] });
      onOpenChange(false);
    },
  });

  return (
    <Dialog open={!!patient} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader><DialogTitle>Edit Recipient of Care</DialogTitle></DialogHeader>
        {patient && (
          <>
            <div className="rounded-lg border border-teal-200 bg-teal-50 px-3 py-2 text-xs text-teal-800 mono">{patient.art_number}</div>
            <div><Label className="mb-1.5 block">Full Name</Label><Input value={fullName} onChange={(e) => setFullName(e.target.value)} /></div>
            <div>
              <Label className="mb-1.5 block">Treatment Combination</Label>
              <Select value={combo} onValueChange={setCombo}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>{TREATMENT_COMBOS.map((t) => <SelectItem key={t} value={t}>{t}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-2 gap-2.5">
              <div>
                <Label className="mb-1.5 block">Progress Status</Label>
                <Select value={status} onValueChange={setStatus}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>{PROGRESS_STATUSES.map((s) => <SelectItem key={s} value={s}>{s.replace(/_/g, " ")}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div><Label className="mb-1.5 block">CD4 Count</Label><Input type="number" value={cd4} onChange={(e) => setCd4(e.target.value)} /></div>
            </div>
            {mutation.isError && <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-800">{mutation.error.message}</div>}
            <Button className="w-full" disabled={!fullName || mutation.isPending} onClick={() => mutation.mutate()}>
              {mutation.isPending ? "Saving..." : "Save Changes"}
            </Button>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

function DeactivatePatientDialog({ patient, onOpenChange }: { patient: Patient | null; onOpenChange: (v: boolean) => void }) {
  const qc = useQueryClient();
  const mutation = useMutation({
    mutationFn: () => api.deactivatePatient(patient!.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["patients"] });
      onOpenChange(false);
    },
  });

  return (
    <Dialog open={!!patient} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader><DialogTitle>Deactivate Recipient of Care</DialogTitle></DialogHeader>
        {patient && (
          <>
            <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
              This deactivates <strong>{patient.full_name}</strong> ({patient.art_number}) — they'll stop
              appearing in active lists and dashboard counts. Their full medical record, dispense history,
              and VL history are kept intact and are not deleted. This can be reversed by a system administrator.
            </div>
            {mutation.isError && <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-800">{mutation.error.message}</div>}
            <Button variant="destructive" className="w-full" disabled={mutation.isPending} onClick={() => mutation.mutate()}>
              {mutation.isPending ? "Deactivating..." : "Deactivate Patient"}
            </Button>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
