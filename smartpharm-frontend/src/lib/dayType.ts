/**
 * Clinic day-type classification — the fixed weekly/monthly operating
 * pattern used across MOHCC facility diaries (confirmed against real
 * paper diary photos + facility description):
 *
 *   - First 2 calendar days of the month  -> STATISTICS (reporting days)
 *   - Every Wednesday                      -> REGISTRATION (new patient intake)
 *   - Every Sunday                         -> CLOSED (not a working day)
 *   - Saturdays                            -> CLOSED, except 2 designated
 *     Saturdays/month reserved for Peads, Infant & Adolescent visits
 *   - Everything else (Mon/Tue/Thu/Fri)    -> NORMAL clinic operations
 *
 * ASSUMPTION FLAGGED: which 2 Saturdays are the Peads/Infant/Adolescent
 * slots wasn't fully specified — this defaults to the 1st and 3rd
 * Saturday of the month. If the real facility pattern is different
 * (e.g. 2nd/4th, or a fixed date), change PEADS_SATURDAY_WEEKS below —
 * it's the only thing in this file that's a guess rather than a
 * confirmed rule.
 */

export type DayType = "STATISTICS" | "REGISTRATION" | "PEADS_CLINIC" | "CLOSED" | "NORMAL";

const PEADS_SATURDAY_WEEKS = [1, 3]; // 1st and 3rd Saturday — see docstring above

export function getDayType(dateStr: string): DayType {
  const d = new Date(`${dateStr}T00:00:00`);
  const dayOfMonth = d.getDate();
  const dayOfWeek = d.getDay(); // 0 = Sunday, 6 = Saturday

  if (dayOfMonth <= 2) return "STATISTICS";
  if (dayOfWeek === 0) return "CLOSED";
  if (dayOfWeek === 6) {
    const weekOfMonth = Math.ceil(dayOfMonth / 7);
    return PEADS_SATURDAY_WEEKS.includes(weekOfMonth) ? "PEADS_CLINIC" : "CLOSED";
  }
  if (dayOfWeek === 3) return "REGISTRATION";
  return "NORMAL";
}

export const DAY_TYPE_STYLE: Record<DayType, { label: string; bg: string; text: string; dot: string }> = {
  STATISTICS:   { label: "Statistics day",              bg: "bg-purple-100",  text: "text-purple-800",  dot: "bg-purple-500" },
  REGISTRATION: { label: "Registration day",            bg: "bg-blue-100",    text: "text-blue-800",    dot: "bg-blue-500" },
  PEADS_CLINIC: { label: "Peads / Infant / Adolescent",  bg: "bg-pink-100",    text: "text-pink-800",    dot: "bg-pink-500" },
  CLOSED:       { label: "Closed",                       bg: "bg-slate-200",   text: "text-slate-500",   dot: "bg-slate-400" },
  NORMAL:       { label: "Normal clinic day",             bg: "",               text: "",                 dot: "" },
};
