import { createFileRoute } from "@tanstack/react-router";
import {
  LogIn, QrCode, Activity, Bot, Hash, Pill, Share2, BarChart3, Upload, Download, Info,
} from "lucide-react";
import { Card } from "@/components/ui/card";

export const Route = createFileRoute("/_authenticated/help")({
  component: HelpPage,
});

const TOPICS = [
  { icon: LogIn, title: "Login & Facility Selection", body: "Select Province → District → Facility, then enter credentials. Demo logins: pharmacist / pharm123 or admin / admin123. Default scan PIN: 1234." },
  { icon: QrCode, title: "QR Code Scanning", body: "Open Scan QR in the Stock Register, enter the 4-digit PIN for a secure 5-minute session, then scan a GS1 pharmaceutical barcode (auto-fills batch, expiry, GTIN) or use Simulate Scan for a demo." },
  { icon: Activity, title: "Early Case Identification", body: "Patients are auto-flagged per MOHCC guidelines: new initiation or RTT with CD4 < 200, or treatment failure (VL ≥ 1000)." },
  { icon: Bot, title: "AI Agent & API Key", body: "Set ANTHROPIC_API_KEY in the backend environment before running uvicorn — never in the frontend. Demo responses work without a key." },
  { icon: Hash, title: "ART Number Format", body: "Zimbabwe format: 09-0A-06-2015-A-00250 — Province · Programme · District · Year · Sequence number." },
  { icon: Pill, title: "Treatment Combinations", body: "Supported: TLD, TLE600, AZT+NVP, TDF+3TC+EFV, TDF+3TC+NVP, AZT+NVP+3TC+EFV, ABC, 2nd Line, 3HP, INH." },
  { icon: Share2, title: "Stock Network — Smart Finder", body: "Safe-to-Donate = Stock − (ADC × 120). Results are ranked by full-coverage capability, then surplus, then proximity." },
  { icon: BarChart3, title: "Forecast Kanban", body: "Drugs sit in Critical / Low / Moderate / Adequate columns by Days of Stock Remaining (30/90/180-day cutoffs)." },
  { icon: Upload, title: "EHR Import Formats", body: "Upload CSV or XLSX for Viral Load results, HTS records, or ART appointment lists — column names must match the templates shown on the EHR Import page." },
  { icon: Download, title: "Export Formats", body: "Download patient, stock, and dispense data as CSV, XLSX, PDF, DOCX, or TXT from Reports & Export." },
];

function HelpPage() {
  return (
    <div className="space-y-4">
      <div>
        <div className="text-lg font-extrabold text-foreground">Help &amp; Documentation</div>
        <div className="text-xs text-muted-foreground mt-0.5">SIEAL v2.0 — RESILIENCE-ART</div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
        {TOPICS.map((t) => {
          const Icon = t.icon;
          return (
            <Card key={t.title} className="p-4">
              <div className="flex items-center gap-2 mb-2">
                <div className="w-7 h-7 rounded-md bg-teal-50 flex items-center justify-center flex-shrink-0">
                  <Icon className="h-3.5 w-3.5 text-teal-700" />
                </div>
                <div className="text-sm font-bold text-foreground">{t.title}</div>
              </div>
              <div className="text-xs text-muted-foreground leading-relaxed">{t.body}</div>
            </Card>
          );
        })}
      </div>
      <div className="flex items-start gap-2 rounded-lg border border-border bg-muted/40 px-3.5 py-2.5 text-[11px] text-muted-foreground">
        <Info className="h-3.5 w-3.5 flex-shrink-0 mt-0.5" />
        Full API reference is available at your backend's <code className="mono">/docs</code> endpoint.
      </div>
    </div>
  );
}
