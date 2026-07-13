import { cn } from "@/lib/utils";
import { getDayType, DAY_TYPE_STYLE } from "@/lib/dayType";

export interface CalendarDay {
  date: string;
  pharmacy_count: number;
  clinical_count: number;
  total: number;
}

/**
 * Section 5: Mini Calendar — now cohort-aware. Each day that has
 * appointments due shows a small two-segment bar: teal = pharmacy visits
 * (6-month cohorts), blue = clinical visits (3-month cohorts), so a
 * pharmacist sees at a glance not just "busy day" but what KIND of busy —
 * a day that's all pharmacy refills is a very different staffing need
 * than one that's mostly clinical reviews.
 */
export function MiniCalendar({ days }: { days: CalendarDay[] }) {
  const byDate = new Map(days.map((d) => [d.date, d]));
  const now = new Date();
  const yr = now.getFullYear();
  const mo = now.getMonth();
  const first = new Date(yr, mo, 1).getDay();
  const daysInMonth = new Date(yr, mo + 1, 0).getDate();
  const dayNames = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"];
  const cells: (number | null)[] = [...Array(first).fill(null), ...Array.from({ length: daysInMonth }, (_, i) => i + 1)];

  return (
    <div>
      <div className="grid grid-cols-7 gap-px mb-1">
        {dayNames.map((d) => (
          <div key={d} className="text-[9px] font-bold text-muted-foreground text-center uppercase">{d}</div>
        ))}
      </div>
      <div className="grid grid-cols-7 gap-px">
        {cells.map((d, i) => {
          if (d === null) return <div key={i} />;
          const isToday = d === now.getDate();
          const dateStr = `${yr}-${String(mo + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
          const day = byDate.get(dateStr);
          const dayType = getDayType(dateStr);
          const typeStyle = DAY_TYPE_STYLE[dayType];
          const total = day?.total ?? 0;
          const pharmPct = total > 0 ? (day!.pharmacy_count / total) * 100 : 0;
          const titleParts = [typeStyle.label];
          if (total > 0) titleParts.push(`${day!.pharmacy_count} pharmacy (6mo) · ${day!.clinical_count} clinical (3mo)`);
          return (
            <div
              key={i}
              title={titleParts.join(" — ")}
              className={cn(
                "aspect-square min-h-[24px] rounded flex flex-col items-center justify-center text-[10px] font-medium relative cursor-pointer transition-colors overflow-hidden",
                isToday ? "bg-teal-700 text-white font-bold" : dayType !== "NORMAL" ? cn(typeStyle.bg, typeStyle.text) : "text-slate-600 hover:bg-teal-50"
              )}
            >
              {d}
              {total > 0 && dayType !== "CLOSED" && (
                <div className="absolute bottom-0 left-0 right-0 h-1 flex">
                  {day!.pharmacy_count > 0 && (
                    <div className={isToday ? "bg-teal-200" : "bg-teal-500"} style={{ width: `${pharmPct}%` }} />
                  )}
                  {day!.clinical_count > 0 && (
                    <div className={isToday ? "bg-blue-200" : "bg-blue-500"} style={{ width: `${100 - pharmPct}%` }} />
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
      <div className="flex items-center gap-2.5 mt-2 text-[9px] text-muted-foreground flex-wrap">
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-teal-500 inline-block" /> Pharmacy (6mo)</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-blue-500 inline-block" /> Clinical (3mo)</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-purple-500 inline-block" /> Statistics</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-blue-400 inline-block" /> Registration (Wed)</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-pink-500 inline-block" /> Peads/Infant/Adolescent</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-slate-400 inline-block" /> Closed</span>
      </div>
    </div>
  );
}
