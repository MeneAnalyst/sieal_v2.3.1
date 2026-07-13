import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Megaphone, Plus, X, AlertCircle, Info, ShieldAlert } from "lucide-react";
import { api } from "@/lib/api";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";

const PRIORITY_STYLE: Record<string, { bg: string; text: string; icon: typeof Info }> = {
  INFO: { bg: "bg-blue-50 border-blue-200", text: "text-blue-800", icon: Info },
  WARNING: { bg: "bg-amber-50 border-amber-200", text: "text-amber-800", icon: AlertCircle },
  URGENT: { bg: "bg-red-50 border-red-200", text: "text-red-800", icon: ShieldAlert },
};

export function NoticeBoard() {
  const [addOpen, setAddOpen] = useState(false);
  const { data: notices = [] } = useQuery({ queryKey: ["notices"], queryFn: api.notices });
  const qc = useQueryClient();
  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.deleteNotice(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notices"] }),
  });

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <CardTitle className="flex items-center gap-1.5"><Megaphone className="h-4 w-4 text-teal-600" /> Notice Board</CardTitle>
        <Button size="sm" variant="outline" className="h-7 gap-1 text-[11px]" onClick={() => setAddOpen(true)}>
          <Plus className="h-3 w-3" /> Post
        </Button>
      </CardHeader>
      <CardContent className="space-y-2 max-h-64 overflow-y-auto">
        {notices.length === 0 && (
          <div className="text-center py-8 text-xs text-muted-foreground">No active notices — post one to share with your facility.</div>
        )}
        {notices.map((n) => {
          const style = PRIORITY_STYLE[n.priority] ?? PRIORITY_STYLE.INFO;
          const Icon = style.icon;
          return (
            <div key={n.id} className={`rounded-lg border px-3 py-2 text-xs ${style.bg} ${style.text} relative group`}>
              <button
                onClick={() => deleteMutation.mutate(n.id)}
                className="absolute top-1.5 right-1.5 opacity-0 group-hover:opacity-100 transition-opacity hover:bg-black/5 rounded p-0.5"
                title="Remove notice"
              >
                <X className="h-3 w-3" />
              </button>
              <div className="flex items-start gap-1.5 pr-4">
                <Icon className="h-3.5 w-3.5 flex-shrink-0 mt-0.5" />
                <div className="min-w-0">
                  <div className="font-semibold">{n.title}</div>
                  <div className="mt-0.5 opacity-90">{n.message}</div>
                  <div className="mt-1 text-[10px] opacity-60">
                    {n.facility_name} · {n.created_by ?? "Unknown"} · {n.created_at}
                    {n.expires_at && <> · expires {n.expires_at}</>}
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </CardContent>
      <AddNoticeDialog open={addOpen} onOpenChange={setAddOpen} />
    </Card>
  );
}

function AddNoticeDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  const qc = useQueryClient();
  const [title, setTitle] = useState("");
  const [message, setMessage] = useState("");
  const [priority, setPriority] = useState("INFO");
  const [scope, setScope] = useState<"global" | "facility">("facility");
  const [expiresAt, setExpiresAt] = useState("");

  const mutation = useMutation({
    mutationFn: () => api.createNotice({ title, message, priority, scope, expires_at: expiresAt || null }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["notices"] });
      setTitle(""); setMessage(""); setPriority("INFO"); setExpiresAt("");
      onOpenChange(false);
    },
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader><DialogTitle>Post a Notice</DialogTitle></DialogHeader>
        <div><Label className="mb-1.5 block">Title</Label><Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Facility closed for stock take" /></div>
        <div><Label className="mb-1.5 block">Message</Label><Textarea value={message} onChange={(e) => setMessage(e.target.value)} rows={3} /></div>
        <div className="grid grid-cols-2 gap-2.5">
          <div>
            <Label className="mb-1.5 block">Priority</Label>
            <Select value={priority} onValueChange={setPriority}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="INFO">Info</SelectItem>
                <SelectItem value="WARNING">Warning</SelectItem>
                <SelectItem value="URGENT">Urgent</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label className="mb-1.5 block">Visible to</Label>
            <Select value={scope} onValueChange={(v) => setScope(v as "global" | "facility")}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="facility">My facility only</SelectItem>
                <SelectItem value="global">All facilities</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
        <div><Label className="mb-1.5 block">Expires (optional)</Label><Input type="date" value={expiresAt} onChange={(e) => setExpiresAt(e.target.value)} /></div>
        {mutation.isError && <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-800">{mutation.error.message}</div>}
        <Button className="w-full" disabled={!title || !message || mutation.isPending} onClick={() => mutation.mutate()}>
          {mutation.isPending ? "Posting..." : "Post Notice"}
        </Button>
      </DialogContent>
    </Dialog>
  );
}
