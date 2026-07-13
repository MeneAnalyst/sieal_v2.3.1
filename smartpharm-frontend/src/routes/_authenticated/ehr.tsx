import { createFileRoute } from "@tanstack/react-router";
import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileUp, FlaskConical, Activity, CalendarClock, Pill, Info, ShieldAlert } from "lucide-react";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

export const Route = createFileRoute("/_authenticated/ehr")({
  component: EhrPage,
});

const DATASETS = [
  { key: "vl-import" as const, title: "Viral Load Results", sub: "VL results with auto-suppression detection (VL < 1000 = suppressed)", icon: FlaskConical, color: "#0D9488", cols: "art_number, sample_date, result_date, vl_result", tplKey: "vl_csv" as const },
  { key: "hts-import" as const, title: "HTS Records", sub: "HIV Testing Service records — accepts a real MOHCC HTS Register export directly", icon: Activity, color: "#3B82F6", cols: "art_number, test_date, result, cd4_count", tplKey: "hts_csv" as const },
  { key: "art-appointments-import" as const, title: "ART Appointments", sub: "Accepts a real MOHCC Art Appointments List export — can auto-register new patients", icon: CalendarClock, color: "#8B5CF6", cols: "art_number, last_visit, next_appointment, visit_type, progress_status", tplKey: "appointments_csv" as const },
  { key: "pharmacy-register-import" as const, title: "Pharmacy Register", sub: "Dispense events — updates real stock via FEFO, same as a manual dispense", icon: Pill, color: "#F59E0B", cols: "art_number, drug_name, quantity, dispense_date, batch_number", tplKey: "pharmacy_register_csv" as const },
];

function EhrPage() {
  useQuery({ queryKey: ["ehr-templates"], queryFn: api.ehrTemplates });

  return (
    <div className="space-y-4">
      <div>
        <div className="text-lg font-extrabold text-foreground">EHR Import</div>
        <div className="text-xs text-muted-foreground mt-0.5">Import from VL, HTS, ART appointment, and pharmacy register data files</div>
      </div>

      <div className="flex items-start gap-2 rounded-lg border border-blue-200 bg-blue-50 px-3.5 py-2.5 text-xs text-blue-800">
        <Info className="h-4 w-4 flex-shrink-0 mt-0.5" />
        <div>
          Supported file formats: <strong>CSV</strong> and <strong>XLSX/XLS</strong> — including real MOHCC/OpenMRS
          report exports (messy report headers are detected and skipped automatically). ART numbers are matched
          case-insensitively; rows that don't match are reported below the upload, not silently dropped.
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        {DATASETS.map((d) => <ImportCard key={d.key} dataset={d} />)}
      </div>
    </div>
  );
}

function ImportCard({ dataset }: { dataset: (typeof DATASETS)[number] }) {
  const qc = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);
  const [result, setResult] = useState<Awaited<ReturnType<typeof api.ehrImport>> | null>(null);

  const Icon = dataset.icon;

  const mutation = useMutation({
    mutationFn: (file: File) => api.ehrImport(dataset.key, file),
    onSuccess: (res) => {
      setResult(res);
      qc.invalidateQueries({ queryKey: ["patients"] });
      qc.invalidateQueries({ queryKey: ["dashboard-summary"] });
      qc.invalidateQueries({ queryKey: ["stock"] });
    },
    onError: (e) => setResult({ imported: 0, skipped: 0, errors: [e instanceof Error ? e.message : "Import failed"] }),
  });

  return (
    <Card className="p-4">
      <div className="w-9 h-9 rounded-lg flex items-center justify-center mb-2.5" style={{ background: `${dataset.color}18` }}>
        <Icon className="h-4 w-4" style={{ color: dataset.color }} />
      </div>
      <div className="text-sm font-bold text-foreground mb-1">{dataset.title}</div>
      <div className="text-[11px] text-muted-foreground mb-3">{dataset.sub}</div>
      <div className="bg-muted/50 rounded-lg p-2.5 mb-3">
        <div className="text-[9px] font-bold uppercase tracking-wide text-muted-foreground mb-1">Simple Template Columns</div>
        <code className="mono text-[10px] text-teal-700">{dataset.cols}</code>
      </div>
      <input
        ref={inputRef} type="file" accept=".csv,.xlsx,.xls" className="hidden"
        onChange={(e) => { const f = e.target.files?.[0]; if (f) mutation.mutate(f); }}
      />
      <Button size="sm" className="w-full gap-1.5" onClick={() => inputRef.current?.click()} disabled={mutation.isPending}>
        <FileUp className="h-3.5 w-3.5" /> {mutation.isPending ? "Uploading..." : "Upload File"}
      </Button>

      {result && (
        <div className="mt-2 space-y-1.5 text-[11px]">
          {result.format_detected && (
            <Badge variant="blue" className="text-[10px]">{result.format_detected}</Badge>
          )}

          <div className="text-emerald-700 font-semibold">
            Imported: {result.imported}
            {typeof result.created === "number" && result.created > 0 && <> · New patients registered: {result.created}</>}
            {" "}· Skipped: {result.skipped}
          </div>

          {!!result.positive_results_for_review?.length && (
            <div className="rounded-md border border-red-200 bg-red-50 px-2.5 py-2 text-red-800">
              <div className="flex items-center gap-1.5 font-semibold mb-1.5">
                <ShieldAlert className="h-3.5 w-3.5 flex-shrink-0" />
                {result.positive_results_for_review.length} positive result(s) need manual review
              </div>
              <div className="text-[10px] text-red-700 mb-1.5">
                Not auto-linked to any patient — matching by name alone risks attaching a result to the wrong
                person. Cross-reference each against the patient's own record.
              </div>
              <div className="space-y-1 max-h-40 overflow-y-auto">
                {result.positive_results_for_review.map((r) => (
                  <div key={r.row} className="bg-white/60 rounded px-2 py-1">
                    <div className="font-semibold">{r.name} · {r.gender}</div>
                    <div className="text-red-700">{r.test_date} — {r.entry_point}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {!!result.skipped_art_numbers?.length && (
            <div className="rounded-md border border-amber-200 bg-amber-50 px-2 py-1.5 text-amber-800">
              <div className="font-semibold mb-0.5">Skipped — ART number not found in system:</div>
              <div className="mono break-all">{result.skipped_art_numbers.join(", ")}</div>
              <div className="mt-1 text-[10px] text-amber-700">
                Check these are registered patients and the ART number matches (case doesn't matter, but the
                numbers/dashes must be identical).
              </div>
            </div>
          )}

          {!!result.errors?.length && (
            <div className="rounded-md border border-red-200 bg-red-50 px-2 py-1.5 text-red-800">
              <div className="font-semibold mb-0.5">Row errors:</div>
              <ul className="list-disc list-inside space-y-0.5">
                {result.errors.map((e, i) => <li key={i}>{e}</li>)}
              </ul>
            </div>
          )}

          {result.data_note && (
            <div className="rounded-md border border-blue-200 bg-blue-50 px-2 py-1.5 text-blue-800 text-[10px]">
              {result.data_note}
            </div>
          )}
        </div>
      )}
    </Card>
  );
}
