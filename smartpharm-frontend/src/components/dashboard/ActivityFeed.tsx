import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { Activity, ShieldAlert } from "lucide-react";
import { api } from "@/lib/api";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export function ActivityFeed() {
  const { data: feed = [], isLoading } = useQuery({ queryKey: ["activity-feed"], queryFn: () => api.activityFeed(15) });

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-1.5"><Activity className="h-4 w-4 text-teal-600" /> Latest Activity</CardTitle>
      </CardHeader>
      <CardContent className="space-y-1.5 max-h-64 overflow-y-auto">
        {isLoading && <div className="text-center py-8 text-xs text-muted-foreground">Loading...</div>}
        {!isLoading && feed.length === 0 && (
          <div className="text-center py-8 text-xs text-muted-foreground">No dispense activity recorded yet</div>
        )}
        {feed.map((item) => (
          <Link
            key={item.id}
            to="/patients/$patientId"
            params={{ patientId: String(item.client_id) }}
            className={`flex items-start gap-2 rounded-lg border px-2.5 py-1.5 text-xs transition-colors hover:bg-muted/40 ${
              item.is_eci_flag ? "border-red-200 bg-red-50/50" : "border-transparent"
            }`}
          >
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-1.5 flex-wrap">
                <span className="font-semibold text-foreground">{item.client_name}</span>
                <span className="text-muted-foreground">dispensed</span>
                <span className="font-medium">{item.quantity} × {item.drug_name.split("(")[0].trim()}</span>
                {item.is_eci_flag && (
                  <Badge variant="red" className="gap-0.5 text-[9px]"><ShieldAlert className="h-2.5 w-2.5" /> ECI</Badge>
                )}
              </div>
              {item.is_eci_flag && item.eci_reason && (
                <div className="text-red-700 text-[10px] mt-0.5">{item.eci_reason}</div>
              )}
              <div className="text-[10px] text-muted-foreground mt-0.5">
                {item.art_number} · {item.dispense_date} · {item.dispensed_by ?? "Unknown"}
              </div>
            </div>
          </Link>
        ))}
      </CardContent>
    </Card>
  );
}
