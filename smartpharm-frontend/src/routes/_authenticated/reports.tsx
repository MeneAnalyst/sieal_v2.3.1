import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Download, FileText, Loader2, Calculator, Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";

export const Route = createFileRoute("/_authenticated/reports")({
  component: ReportsPage,
});

const DATASETS = [
  { key: "patients" as const, label: "Patient Register" },
  { key: "stock" as const, label: "Stock Inventory" },
  { key: "dispenses" as const, label: "Dispense History" },
  { key: "losses" as const, label: "Expiry Loss Register" },
  { key: "eci" as const, label: "ECI Register" },
  { key: "transfers" as const, label: "Network Transfer Register" },
];

const FORMATS = [
  { key: "csv", label: "CSV" }, { key: "xlsx", label: "XLSX" }, { key: "pdf", label: "PDF" },
  { key: "docx", label: "DOCX" }, { key: "txt", label: "TXT" }, { key: "json", label: "JSON" },
];

const AI_REPORTS = [
  { key: "monthly_summary", label: "Monthly Operations Summary" },
  { key: "eci_analysis", label: "ECI Clinical Analysis" },
  { key: "stock_intelligence", label: "Stock Intelligence Report" },
  { key: "adherence_narrative", label: "Adherence & Retention" },
  { key: "anomaly_detection", label: "Anomaly Detection Report" },
];

function ReportsPage() {
  const [dataset, setDataset] = useState<(typeof DATASETS)[number]["key"]>("patients");
  const [format, setFormat] = useState("xlsx");
  const [reportContent, setReportContent] = useState<{ title: string; content: string; source?: "template" | "claude"; note?: string } | null>(null);

  const downloadMutation = useMutation({ mutationFn: () => api.downloadExport(dataset, format) });
  const reportMutation = useMutation({
    mutationFn: (type: string) => api.aiReport(type),
    onSuccess: (res, type) => setReportContent({ title: AI_REPORTS.find((r) => r.key === type)?.label ?? "Report", content: res.content, source: res.source, note: res.note }),
  });

  return (
    <div className="space-y-4">
      <div>
        <div className="text-lg font-extrabold text-foreground">Reports &amp; Export</div>
        <div className="text-xs text-muted-foreground mt-0.5">Multi-format data export and AI-generated clinical reports</div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <CardHeader><CardTitle>Export as...</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <div className="grid grid-cols-2 gap-2.5">
              <div>
                <div className="text-[10px] font-bold uppercase tracking-wide text-muted-foreground mb-1.5">Dataset</div>
                <Select value={dataset} onValueChange={(v) => setDataset(v as typeof dataset)}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>{DATASETS.map((d) => <SelectItem key={d.key} value={d.key}>{d.label}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div>
                <div className="text-[10px] font-bold uppercase tracking-wide text-muted-foreground mb-1.5">Format</div>
                <Select value={format} onValueChange={setFormat}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>{FORMATS.map((f) => <SelectItem key={f.key} value={f.key}>{f.label}</SelectItem>)}</SelectContent>
                </Select>
              </div>
            </div>
            <Button className="w-full gap-1.5" disabled={downloadMutation.isPending} onClick={() => downloadMutation.mutate()}>
              {downloadMutation.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Download className="h-3.5 w-3.5" />}
              Download {dataset}.{format}
            </Button>
            {downloadMutation.isError && (
              <div className="text-xs text-red-600">{downloadMutation.error instanceof Error ? downloadMutation.error.message : "Export failed"}</div>
            )}
            <p className="text-[10px] text-muted-foreground leading-relaxed">
              Calls <code className="mono bg-muted px-1 rounded">GET /api/export/{"{dataset}"}?format={"{format}"}</code> —
              PDF via reportlab with a facility header and timestamp, XLSX as a multi-sheet workbook (Summary + Data).
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>AI-Generated Reports</CardTitle></CardHeader>
          <CardContent className="space-y-1.5">
            {AI_REPORTS.map((r) => (
              <div key={r.key} className="flex items-center justify-between py-1.5 border-b border-border/60 last:border-0">
                <span className="text-xs flex items-center gap-1.5"><FileText className="h-3 w-3 text-teal-600" /> {r.label}</span>
                <Button size="sm" onClick={() => reportMutation.mutate(r.key)} disabled={reportMutation.isPending}>
                  Generate
                </Button>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      {reportMutation.isPending && (
        <Card><CardContent className="py-8 text-center text-xs text-muted-foreground">Generating report...</CardContent></Card>
      )}

      {reportContent && (
        <Card>
          <CardHeader>
            <CardTitle>{reportContent.title}</CardTitle>
            <Button size="sm" variant="outline" onClick={() => setReportContent(null)}>Close</Button>
          </CardHeader>
          <CardContent>
            <div className="bg-teal-50 border border-teal-100 rounded-lg p-4 text-sm whitespace-pre-wrap leading-relaxed">
              {reportContent.content}
            </div>
            {reportContent.source && (
              <div className="flex items-center gap-1.5 mt-2">
                {reportContent.source === "claude" ? (
                  <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-teal-700 bg-teal-50 border border-teal-100 rounded-full px-2 py-0.5">
                    <Sparkles className="h-2.5 w-2.5" /> AI-enhanced
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-slate-600 bg-slate-100 border border-slate-200 rounded-full px-2 py-0.5">
                    <Calculator className="h-2.5 w-2.5" /> Computed
                  </span>
                )}
                {reportContent.note && <span className="text-[10px] text-muted-foreground">{reportContent.note}</span>}
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
