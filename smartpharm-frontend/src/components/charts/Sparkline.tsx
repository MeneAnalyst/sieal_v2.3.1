import { LineChart, Line, ResponsiveContainer, YAxis } from "recharts";

/**
 * Section 5: Patient/Stock Sparkline.
 * Reasoning: shows the *direction* of the trend (rising/falling consumption),
 * which is what lets a pharmacist anticipate a stockout before DSR hits
 * the Critical band — a single number can't convey momentum.
 */
export function Sparkline({ data, color = "#14B8A6" }: { data: number[]; color?: string }) {
  if (!data || data.length < 2) return <div className="h-6" />;
  const points = data.map((v, i) => ({ i, v }));
  return (
    <ResponsiveContainer width={72} height={24}>
      <LineChart data={points} margin={{ top: 2, right: 2, bottom: 2, left: 2 }}>
        <YAxis hide domain={["dataMin", "dataMax"]} />
        <Line type="monotone" dataKey="v" stroke={color} strokeWidth={1.8} dot={false} isAnimationActive={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}
