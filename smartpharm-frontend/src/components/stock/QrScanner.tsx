import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { QrCode, ShieldCheck, Zap, Camera } from "lucide-react";
import { api } from "@/lib/api";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from "@/components/ui/select";

type Step = "pin" | "scan";

/** GS1 Application Identifier parsing — (01) GTIN, (17) expiry YYMMDD, (10) batch/lot. */
function parseGS1(raw: string) {
  const gtin = raw.match(/\(01\)(\d{14})/)?.[1] ?? null;
  const expMatch = raw.match(/\(17\)(\d{6})/)?.[1];
  const expiry = expMatch ? `20${expMatch.slice(0, 2)}-${expMatch.slice(2, 4)}-${expMatch.slice(4, 6)}` : null;
  const batch = raw.match(/\(10\)([^(]+)/)?.[1]?.trim() ?? null;
  return { gtin, expiry, batch };
}

const SIM_CODES = [
  "(01)03475900014006(17)271231(10)TLD-ZW-SIM-001",
  "(01)05060370990126(17)261015(10)CTX-ZW-SIM-001",
  "(01)04035680150498(17)280630(10)AZT-ZW-SIM-001",
];

export function ScanStockDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  const qc = useQueryClient();
  const [step, setStep] = useState<Step>("pin");
  const [pin, setPin] = useState("");
  const [pinError, setPinError] = useState("");
  const [cameraError, setCameraError] = useState(false);
  const scannerRef = useRef<{ stop: () => Promise<void> } | null>(null);
  const scanBoxRef = useRef<HTMLDivElement>(null);

  const [drugId, setDrugId] = useState("");
  const [batch, setBatch] = useState("");
  const [expiry, setExpiry] = useState("");
  const [gtin, setGtin] = useState("");
  const [qty, setQty] = useState("");
  const [lastScanMsg, setLastScanMsg] = useState("");

  const { data: drugs = [] } = useQuery({ queryKey: ["drugs"], queryFn: api.drugs, enabled: step === "scan" });

  const verifyPin = useMutation({
    mutationFn: () => api.verifyPin(pin),
    onSuccess: () => { setStep("scan"); setPinError(""); },
    onError: (e) => setPinError(e instanceof Error ? e.message : "Incorrect PIN"),
  });

  const receiveMutation = useMutation({
    mutationFn: () => api.receiveStock({
      drug_id: Number(drugId), batch_number: batch, expiry_date: expiry,
      quantity_received: Number(qty), gtin: gtin || null, scan_logged: 1,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["stock"] });
      qc.invalidateQueries({ queryKey: ["stock-alerts"] });
      qc.invalidateQueries({ queryKey: ["dsr"] });
      reset();
      onOpenChange(false);
    },
  });

  function reset() {
    setStep("pin"); setPin(""); setPinError(""); setDrugId(""); setBatch(""); setExpiry(""); setGtin(""); setQty(""); setLastScanMsg("");
  }

  function handleDecoded(raw: string) {
    const parsed = parseGS1(raw);
    if (parsed.batch) setBatch(parsed.batch);
    if (parsed.expiry) setExpiry(parsed.expiry);
    if (parsed.gtin) setGtin(parsed.gtin);
    setLastScanMsg(`Scanned: Batch=${parsed.batch ?? "?"} Exp=${parsed.expiry ?? "?"}`);
    scannerRef.current?.stop().catch(() => {});
  }

  function simulateScan() {
    handleDecoded(SIM_CODES[Math.floor(Math.random() * SIM_CODES.length)]);
  }

  // Start the camera once we're on the scan step and the DOM node exists.
  useEffect(() => {
    if (step !== "scan" || !scanBoxRef.current) return;
    let cancelled = false;

    (async () => {
      try {
        const { Html5Qrcode } = await import("html5-qrcode");
        const instance = new Html5Qrcode(scanBoxRef.current!.id);
        scannerRef.current = instance;
        await instance.start(
          { facingMode: "environment" },
          { fps: 10, qrbox: { width: 240, height: 180 } },
          (decoded) => !cancelled && handleDecoded(decoded),
          () => {}
        );
      } catch {
        if (!cancelled) setCameraError(true);
      }
    })();

    return () => {
      cancelled = true;
      scannerRef.current?.stop().catch(() => {});
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step]);

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) reset(); onOpenChange(v); }}>
      <DialogContent>
        {step === "pin" ? (
          <>
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2"><QrCode className="h-4 w-4" /> QR Scanner — PIN Required</DialogTitle>
              <DialogDescription>Every scan session is logged with timestamp and user ID.</DialogDescription>
            </DialogHeader>
            <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2.5 text-xs text-amber-800 flex gap-2">
              <ShieldCheck className="h-4 w-4 flex-shrink-0 mt-0.5" />
              <span>PIN required to open the scanner. Session expires after 5 minutes. Default demo PIN: <strong>1234</strong>.</span>
            </div>
            <div>
              <Label className="mb-1.5 block">4-Digit Scan PIN</Label>
              <Input
                type="password" maxLength={4} value={pin} onChange={(e) => setPin(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && verifyPin.mutate()}
                placeholder="••••" className="text-center text-lg tracking-[0.5em]"
              />
              {pinError && <div className="text-xs text-red-600 mt-1.5">{pinError}</div>}
            </div>
            <Button className="w-full" disabled={pin.length !== 4 || verifyPin.isPending} onClick={() => verifyPin.mutate()}>
              {verifyPin.isPending ? "Verifying..." : "Verify PIN & Open Scanner"}
            </Button>
          </>
        ) : (
          <>
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2"><Camera className="h-4 w-4" /> QR Stock Receipt</DialogTitle>
              <DialogDescription>Secure session active — 5 minute window — all scans logged.</DialogDescription>
            </DialogHeader>

            <div id="qr-reader-box" ref={scanBoxRef} className="w-full min-h-[140px] rounded-lg bg-muted flex items-center justify-center overflow-hidden">
              {cameraError && (
                <div className="text-center text-xs text-muted-foreground p-5">
                  <Camera className="h-6 w-6 mx-auto mb-2 text-slate-300" />
                  Camera unavailable — use Simulate Scan below.
                </div>
              )}
            </div>

            <Button variant="outline" size="sm" onClick={simulateScan} className="gap-1.5 self-center">
              <Zap className="h-3.5 w-3.5" /> Simulate Scan (Demo)
            </Button>
            {lastScanMsg && <div className="text-[11px] text-emerald-700 text-center -mt-1">{lastScanMsg}</div>}

            <div className="grid grid-cols-2 gap-2.5">
              <div>
                <Label className="mb-1.5 block">Drug *</Label>
                <Select value={drugId} onValueChange={setDrugId}>
                  <SelectTrigger><SelectValue placeholder="Select" /></SelectTrigger>
                  <SelectContent>{drugs.map((d) => <SelectItem key={d.id} value={String(d.id)}>{d.name}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div>
                <Label className="mb-1.5 block">Batch *</Label>
                <Input value={batch} onChange={(e) => setBatch(e.target.value)} placeholder="Auto-filled from scan" />
              </div>
              <div>
                <Label className="mb-1.5 block">Expiry Date *</Label>
                <Input type="date" value={expiry} onChange={(e) => setExpiry(e.target.value)} />
              </div>
              <div>
                <Label className="mb-1.5 block">Quantity *</Label>
                <Input type="number" value={qty} onChange={(e) => setQty(e.target.value)} placeholder="Count physically" />
              </div>
              <div className="col-span-2">
                <Label className="mb-1.5 block">GTIN (from scan)</Label>
                <Input value={gtin} onChange={(e) => setGtin(e.target.value)} placeholder="Auto-filled" />
              </div>
            </div>

            <Button
              className="w-full"
              disabled={!drugId || !batch || !expiry || !qty || receiveMutation.isPending}
              onClick={() => receiveMutation.mutate()}
            >
              {receiveMutation.isPending ? "Confirming..." : "Confirm Receipt"}
            </Button>
            {receiveMutation.isError && (
              <div className="text-xs text-red-600 text-center">
                {receiveMutation.error instanceof Error ? receiveMutation.error.message : "Failed to record receipt"}
              </div>
            )}
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
