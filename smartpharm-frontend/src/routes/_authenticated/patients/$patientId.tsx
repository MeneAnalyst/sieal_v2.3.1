import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { ChevronLeft } from "lucide-react";
import { api } from "@/lib/api";
import { fmtDate } from "@/lib/utils";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { StatisticalGauge } from "@/components/charts/StatisticalGauge";

export const Route = createFileRoute("/_authenticated/patients/$patientId")({
  component: PatientDetailPage,
});

function PatientDetailPage() {
  const { patientId } = Route.useParams();
  const id = Number(patientId);
  const { data: patient, isLoading } = useQuery({ queryKey: ["patient", id], queryFn: () => api.patient(id) });
  const { data: stats } = useQuery({ queryKey: ["patient-stats", id], queryFn: () => api.patientStats(id) });

  if (isLoading || !patient) {
    return <div className="text-center py-20 text-muted-foreground text-sm">Loading patient record...</div>;
  }

  return (
    <div className="space-y-4 max-w-3xl">
      <Link to="/patients" className="inline-flex items-center gap-1 text-xs text-teal-700 hover:underline">
        <ChevronLeft className="h-3.5 w-3.5" /> Back to Recipients of Care
      </Link>

      <div>
        <div className="text-[10px] font-bold uppercase tracking-wide text-muted-foreground">Recipient of Care</div>
        <div className="flex items-center gap-2 mt-0.5">
          <h1 className="text-xl font-extrabold text-foreground">{patient.full_name}</h1>
        </div>
        <div className="flex gap-1.5 mt-1.5">
          <Badge>{patient.art_number}</Badge>
          <Badge variant="gray">{patient.progress_status.replace(/_/g, " ")}</Badge>
          {patient.is_eci_flag && <Badge variant="red">ECI</Badge>}
        </div>
      </div>

      {patient.eci_reason && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-3.5 py-2.5 text-xs text-red-800">{patient.eci_reason}</div>
      )}

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
        <Field label="DOB" value={fmtDate(patient.date_of_birth)} />
        <Field label="Gender" value={patient.gender ?? "—"} />
        <Field label="CD4" value={patient.cd4_count ? `${patient.cd4_count} cells/µL` : "—"} />
        <Field label="VL" value={patient.vl_result ? `${patient.vl_result.toLocaleString()} cp/mL` : "—"} />
        <Field label="Suppressed" value={patient.vl_suppressed ? "Yes" : "No"} />
        <Field label="Adherence" value={patient.adherence_score ? `${patient.adherence_score}%` : "—"} />
        <Field label="Last Visit" value={fmtDate(patient.last_visit)} />
        <Field label="Next Appt" value={fmtDate(patient.next_appointment)} />
      </div>

      <Card>
        <CardHeader><CardTitle>Treatment Combination</CardTitle></CardHeader>
        <CardContent>
          <div className="text-sm font-semibold text-teal-700">{patient.treatment_combination ?? "Not recorded"}</div>
        </CardContent>
      </Card>

      {/* Section 8 — Hypothesis Analysis Integration */}
      {stats && <StatisticalGauge stats={stats} />}
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-muted/50 rounded-lg p-2.5">
      <div className="text-[9px] font-bold uppercase tracking-wide text-muted-foreground">{label}</div>
      <div className="text-sm font-semibold text-foreground mt-0.5">{value}</div>
    </div>
  );
}
