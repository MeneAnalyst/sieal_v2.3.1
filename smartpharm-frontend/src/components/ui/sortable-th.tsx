import { ArrowUp, ArrowDown, ArrowUpDown } from "lucide-react";
import { TableHead } from "@/components/ui/table";
import { cn } from "@/lib/utils";

export type SortDir = "asc" | "desc" | null;

interface SortableThProps {
  label: string;
  sortKey: string;
  activeKey: string | null;
  dir: SortDir;
  onSort: (key: string) => void;
  className?: string;
}

export function SortableTh({ label, sortKey, activeKey, dir, onSort, className }: SortableThProps) {
  const active = activeKey === sortKey;
  return (
    <TableHead
      className={cn("cursor-pointer select-none hover:text-foreground transition-colors", className)}
      onClick={() => onSort(sortKey)}
    >
      <div className="flex items-center gap-1">
        {label}
        {active && dir === "asc" && <ArrowUp className="h-3 w-3" />}
        {active && dir === "desc" && <ArrowDown className="h-3 w-3" />}
        {!active && <ArrowUpDown className="h-3 w-3 opacity-30" />}
      </div>
    </TableHead>
  );
}

/** Generic three-value sorter: null/undefined always sorts last, regardless of direction. */
export function sortRows<T>(rows: T[], key: keyof T | null, dir: SortDir): T[] {
  if (!key || !dir) return rows;
  const sorted = [...rows].sort((a, b) => {
    const av = a[key], bv = b[key];
    if (av === null || av === undefined) return 1;
    if (bv === null || bv === undefined) return -1;
    if (typeof av === "string" && typeof bv === "string") return av.localeCompare(bv);
    if (av < bv) return -1;
    if (av > bv) return 1;
    return 0;
  });
  return dir === "asc" ? sorted : sorted.reverse();
}
