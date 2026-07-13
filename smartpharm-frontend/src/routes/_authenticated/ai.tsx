import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  Bot, Send, ShieldCheck, AlertTriangle, TrendingUp, Info, RefreshCw, Paperclip, X, FileUp,
  Calculator, Sparkles,
} from "lucide-react";
import { api } from "@/lib/api";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import type { ChatMessage, StrategicAlert } from "@/types";

export const Route = createFileRoute("/_authenticated/ai")({
  component: StrategicIntelligencePage,
});

const QUICK_PROMPTS = [
  "Monthly operations summary",
  "ECI analysis for flagged patients",
  "Stock intelligence & procurement",
  "Adherence & retention narrative",
  "Run anomaly detection",
];

const SEVERITY_META: Record<StrategicAlert["severity"], { icon: React.ElementType; color: string; bg: string }> = {
  critical: { icon: AlertTriangle, color: "text-red-700", bg: "bg-red-50 border-red-200" },
  high: { icon: AlertTriangle, color: "text-orange-700", bg: "bg-orange-50 border-orange-200" },
  medium: { icon: TrendingUp, color: "text-amber-700", bg: "bg-amber-50 border-amber-200" },
  info: { icon: Info, color: "text-blue-700", bg: "bg-blue-50 border-blue-200" },
};

/**
 * Every AI Agent response is computed by a deterministic template first;
 * Claude only refines the prose when configured and reachable. This badge
 * makes that visible rather than silent — "Computed" is not a degraded
 * state, it's the reliable default the system falls back to automatically
 * on any API issue (see routers/ai_agent.py's generate_narrative()).
 */
function SourceBadge({ source, note }: { source?: "template" | "claude"; note?: string }) {
  if (!source) return null;
  return (
    <div className="flex items-center gap-1.5 mt-1.5">
      {source === "claude" ? (
        <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-teal-700 bg-teal-50 border border-teal-100 rounded-full px-2 py-0.5">
          <Sparkles className="h-2.5 w-2.5" /> AI-enhanced
        </span>
      ) : (
        <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-slate-600 bg-slate-100 border border-slate-200 rounded-full px-2 py-0.5">
          <Calculator className="h-2.5 w-2.5" /> Computed
        </span>
      )}
      {note && <span className="text-[10px] text-muted-foreground">{note}</span>}
    </div>
  );
}

function StrategicIntelligencePage() {
  return (
    <div className="grid grid-cols-1 xl:grid-cols-[320px_1fr] gap-4 h-full">
      <BriefingFeed />
      <DeepDiveChat />
    </div>
  );
}

/** Left panel — proactive, deterministically-computed alerts, ranked/narrated by the model. */
function BriefingFeed() {
  const { data, isFetching, refetch } = useQuery({ queryKey: ["strategic-brief"], queryFn: api.aiBrief });

  return (
    <div className="space-y-3">
      <Card>
        <CardHeader>
          <CardTitle>Briefing Feed</CardTitle>
          <Button variant="outline" size="icon" className="h-7 w-7" onClick={() => refetch()} disabled={isFetching}>
            <RefreshCw className={`h-3.5 w-3.5 ${isFetching ? "animate-spin" : ""}`} />
          </Button>
        </CardHeader>
        <CardContent className="space-y-2.5">
          {isFetching && !data && <div className="text-xs text-muted-foreground text-center py-6">Scanning facility state...</div>}
          {data?.alerts.length === 0 && (
            <div className="text-xs text-muted-foreground text-center py-6">No elevated risks detected right now.</div>
          )}
          {data?.alerts.map((a, i) => {
            const meta = SEVERITY_META[a.severity];
            const Icon = meta.icon;
            return (
              <div key={i} className={`rounded-lg border px-3 py-2.5 ${meta.bg}`}>
                <div className={`flex items-center gap-1.5 text-xs font-bold ${meta.color}`}>
                  <Icon className="h-3.5 w-3.5 flex-shrink-0" /> {a.title}
                </div>
                <div className="text-[11px] text-muted-foreground mt-1 leading-relaxed">{a.detail}</div>
                <Badge variant="gray" className="mt-1.5">{a.category}</Badge>
              </div>
            );
          })}
        </CardContent>
      </Card>

      {data?.narrative && (
        <Card>
          <CardHeader><CardTitle>Strategic Director — Recommendations</CardTitle></CardHeader>
          <CardContent>
            <div className="text-xs text-foreground whitespace-pre-wrap leading-relaxed">{data.narrative}</div>
            <SourceBadge source={data.source} note={data.note} />
          </CardContent>
        </Card>
      )}

      <Card className="border-t-[3px] border-t-teal-700">
        <CardContent className="pt-4">
          <div className="flex items-center gap-1.5 text-xs font-bold text-foreground mb-2">
            <ShieldCheck className="h-3.5 w-3.5 text-teal-700" /> Key Security
          </div>
          <p className="text-[11px] text-muted-foreground leading-relaxed">
            Every request — briefing, chat, or uploaded-file analysis — is proxied through the backend at{" "}
            <code className="mono text-[10px] bg-muted px-1 rounded">/api/ai_agent/*</code>, which reads{" "}
            <code className="mono text-[10px] bg-muted px-1 rounded">ANTHROPIC_API_KEY</code> from its own
            environment. The key never reaches the browser bundle.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

/** Right panel — chat grounded in JSON context, with optional CSV/TXT data import. */
function DeepDiveChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const chat = useMutation({
    mutationFn: (query: string) => api.aiChat(query),
    onSuccess: (res) => setMessages((m) => [...m, { role: "assistant", content: res.response, source: res.source, note: res.note }]),
    onError: (e) => setMessages((m) => [...m, { role: "assistant", content: e instanceof Error ? e.message : "AI service error" }]),
  });

  const upload = useMutation({
    mutationFn: (file: File) => api.aiAnalyzeUpload(file),
    onSuccess: (res) =>
      setMessages((m) => [...m, {
        role: "assistant",
        content: `Analysis of ${res.filename} (${(res.profile as { row_count: number }).row_count} rows):\n\n${res.response}`,
        source: res.source, note: res.note,
      }]),
    onError: (e) => setMessages((m) => [...m, { role: "assistant", content: e instanceof Error ? e.message : "Import failed" }]),
  });

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  function send(query: string) {
    if (pendingFile) {
      setMessages((m) => [...m, { role: "user", content: `Imported ${pendingFile.name} for analysis${query ? `: "${query}"` : ""}` }]);
      upload.mutate(pendingFile);
      setPendingFile(null);
      setInput("");
      return;
    }
    if (!query.trim()) return;
    setMessages((m) => [...m, { role: "user", content: query }]);
    setInput("");
    chat.mutate(query);
  }

  const isBusy = chat.isPending || upload.isPending;

  return (
    <Card className="flex flex-col">
      <CardHeader><CardTitle className="flex items-center gap-1.5"><Bot className="h-4 w-4" /> Deep Dive — RESILIENCE-ART Analyst</CardTitle></CardHeader>
      <CardContent className="flex-1 flex flex-col min-h-[480px]">
        <div className="flex flex-wrap gap-1.5 mb-3">
          {QUICK_PROMPTS.map((p) => (
            <Button key={p} variant="outline" size="sm" className="h-7 text-[11px]" onClick={() => send(p)} disabled={isBusy}>
              {p}
            </Button>
          ))}
        </div>

        <div ref={scrollRef} className="flex-1 overflow-y-auto space-y-3 mb-3 pr-1">
          {messages.length === 0 && (
            <div className="text-center text-muted-foreground text-xs py-10">
              Ask about patient outcomes, stock intelligence, or treatment failure analysis — or import a CSV
              (VL export, external stock count, DHIS2 pull) using the paperclip below for grounded analysis.
            </div>
          )}
          {messages.map((m, i) => (
            <div key={i} className={m.role === "user" ? "text-right" : ""}>
              <div
                className={
                  m.role === "user"
                    ? "inline-block bg-teal-700 text-white rounded-2xl rounded-br-sm px-3.5 py-2 text-sm max-w-[85%] text-left"
                    : "bg-teal-50 border border-teal-100 rounded-lg px-3.5 py-2.5 text-sm text-foreground whitespace-pre-wrap leading-relaxed"
                }
              >
                {m.content}
              </div>
              {m.role === "assistant" && <SourceBadge source={m.source} note={m.note} />}
            </div>
          ))}
          {isBusy && (
            <div className="bg-teal-50 border border-teal-100 rounded-lg px-3.5 py-2.5 flex gap-1">
              {[0, 1, 2].map((i) => (
                <span key={i} className="w-1.5 h-1.5 rounded-full bg-teal-500 animate-bounce" style={{ animationDelay: `${i * 0.13}s` }} />
              ))}
            </div>
          )}
        </div>

        {pendingFile && (
          <div className="flex items-center gap-2 mb-2 text-xs bg-muted/60 rounded-md px-2.5 py-1.5">
            <FileUp className="h-3.5 w-3.5 text-teal-700 flex-shrink-0" />
            <span className="flex-1 truncate">{pendingFile.name}</span>
            <button onClick={() => setPendingFile(null)} className="text-muted-foreground hover:text-foreground">
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        )}

        <div className="flex gap-2">
          <input
            ref={fileInputRef} type="file" accept=".csv,.txt" className="hidden"
            onChange={(e) => { const f = e.target.files?.[0]; if (f) setPendingFile(f); }}
          />
          <Button variant="outline" size="icon" onClick={() => fileInputRef.current?.click()} disabled={isBusy} title="Import CSV data">
            <Paperclip className="h-3.5 w-3.5" />
          </Button>
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send(input)}
            placeholder={pendingFile ? "Add a note about this data (optional)..." : "Ask about patients, stock, or clinical outcomes..."}
            disabled={isBusy}
          />
          <Button onClick={() => send(input)} disabled={isBusy || (!input.trim() && !pendingFile)}>
            <Send className="h-3.5 w-3.5" />
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
