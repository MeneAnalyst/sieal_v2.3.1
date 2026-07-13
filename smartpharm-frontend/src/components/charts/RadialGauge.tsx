import { RadialBarChart, RadialBar, ResponsiveContainer, PolarAngleAxis } from "recharts";

/**
 * Section 5: Radial Bar Chart.
 * Reasoning: visualizes inventory fill-rate against the 100% target buffer
 * (Section 4C ADEQUATE threshold). A single glance at fill-angle communicates
 * under/over-preparedness faster than reading a percentage in a table cell.
 */
export function RadialGauge({
  label, pct, color, sublabel,
}: { label: string; pct: number; color: string; sublabel?: string }) {
  const data = [{ name: label, value: Math.min(100, Math.max(0, pct)) }];
  return (
    <div className="flex flex-col items-center">
      <div className="relative h-20 w-20">
        <ResponsiveContainer>
          <RadialBarChart
            innerRadius="72%"
            outerRadius="100%"
            barSize={8}
            data={data}
            startAngle={90}
            endAngle={-270}
          >
            <PolarAngleAxis type="number" domain={[0, 100]} angleAxisId={0} tick={false} />
            <RadialBar background={{ fill: "#E2E8F0" }} dataKey="value" cornerRadius={8} fill={color} isAnimationActive={true} />
          </RadialBarChart>
        </ResponsiveContainer>
        <div className="absolute inset-0 flex items-center justify-center text-sm font-black" style={{ color }}>
          {Math.round(pct)}%
        </div>
      </div>
      <div className="mt-1 text-[10px] font-bold uppercase tracking-wide text-muted-foreground text-center">{label}</div>
      {sublabel && <div className="text-[9px] text-muted-foreground">{sublabel}</div>}
    </div>
  );
}
