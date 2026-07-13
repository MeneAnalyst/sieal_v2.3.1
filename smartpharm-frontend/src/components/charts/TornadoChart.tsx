import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Cell, ReferenceLine, Tooltip } from "recharts";

export interface TornadoFactor {
  factor: string;
  /** negative = pulls DSR down (risk), positive = pulls DSR up (buffer) */
  impactDays: number;
}

/**
 * Section 5: Tornado Chart (sensitivity analysis).
 * Reasoning: ranks the factors that move a facility's DSR the most —
 * supplier delay, VL-driven consumption surge, seasonal malaria co-prescribing —
 * so management knows *where* to intervene first, not just *that* stock is low.
 * Bars diverge from a zero baseline and are sorted by |impact|.
 */
export function TornadoChart({ factors }: { factors: TornadoFactor[] }) {
  const sorted = [...factors].sort((a, b) => Math.abs(b.impactDays) - Math.abs(a.impactDays));
  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={sorted} layout="vertical" margin={{ top: 4, right: 16, bottom: 4, left: 8 }}>
        <XAxis type="number" tick={{ fontSize: 10, fill: "#64748B" }} axisLine={false} tickLine={false} />
        <YAxis
          type="category"
          dataKey="factor"
          width={140}
          tick={{ fontSize: 11, fill: "#334155" }}
          axisLine={false}
          tickLine={false}
        />
        <ReferenceLine x={0} stroke="#CBD5E1" />
        <Tooltip
          formatter={(v: number) => [`${v > 0 ? "+" : ""}${v} days DSR`, "Impact"]}
          contentStyle={{ fontSize: 11, borderRadius: 8, borderColor: "#E2E8F0" }}
        />
        <Bar dataKey="impactDays" radius={4} barSize={16}>
          {sorted.map((f, i) => (
            <Cell key={i} fill={f.impactDays < 0 ? "#EF4444" : "#10B981"} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
