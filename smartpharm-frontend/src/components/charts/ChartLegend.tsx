interface LegendItem {
  color: string;
  label: string;
  dashed?: boolean;
}

/**
 * Small swatch-and-label legend row for charts that don't have an obvious
 * built-in one (radial gauges, custom bar colorings). Keeps the same
 * pattern everywhere instead of one-off inline JSX per chart.
 */
export function ChartLegend({ items }: { items: LegendItem[] }) {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 mt-2">
      {items.map((item) => (
        <div key={item.label} className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
          {item.dashed ? (
            <svg width="14" height="8" className="flex-shrink-0">
              <line x1="0" y1="4" x2="14" y2="4" stroke={item.color} strokeWidth="2" strokeDasharray="3 2" />
            </svg>
          ) : (
            <span className="w-2.5 h-2.5 rounded-sm flex-shrink-0" style={{ background: item.color }} />
          )}
          {item.label}
        </div>
      ))}
    </div>
  );
}

/**
 * Plain-language "what am I looking at" caption — same visual treatment
 * everywhere, so charts don't each invent their own ad-hoc helper text style.
 */
export function ChartInterpretation({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-[10px] text-muted-foreground mt-1.5 leading-relaxed flex gap-1.5">
      <span className="flex-shrink-0">💡</span>
      <span>{children}</span>
    </p>
  );
}
