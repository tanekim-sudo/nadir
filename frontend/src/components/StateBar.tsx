"use client";
import type { Company } from "@/lib/api";
import clsx from "clsx";

const STATE_COLORS: Record<string, string> = {
  NORMAL: "bg-gray-600",
  WATCH: "bg-yellow-500",
  NADIR_COMPLETE: "bg-red-500",
  ZENITH: "bg-emerald-500",
  CONSTRAINT_DISSOLVING: "bg-purple-500",
};

const STATE_LABELS: Record<string, string> = {
  NORMAL: "Normal",
  WATCH: "Watch",
  NADIR_COMPLETE: "NADIR Complete",
  ZENITH: "Zenith",
  CONSTRAINT_DISSOLVING: "Dissolving",
};

interface Props {
  companies: Company[];
}

export default function StateBar({ companies }: Props) {
  const counts: Record<string, number> = {};
  for (const c of companies) {
    counts[c.system_state] = (counts[c.system_state] || 0) + 1;
  }
  const total = companies.length || 1;

  return (
    <div className="card">
      <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-gray-400">
        State Distribution
      </p>
      <div className="flex h-6 overflow-hidden rounded-full">
        {Object.entries(STATE_COLORS).map(([state, color]) => {
          const count = counts[state] || 0;
          const pct = (count / total) * 100;
          if (pct === 0) return null;
          return (
            <div
              key={state}
              className={clsx(color, "flex items-center justify-center text-[10px] font-bold text-white transition-all")}
              style={{ width: `${pct}%` }}
              title={`${STATE_LABELS[state]}: ${count}`}
            >
              {pct > 8 ? count : ""}
            </div>
          );
        })}
      </div>
      <div className="mt-2 flex flex-wrap gap-3">
        {Object.entries(STATE_COLORS).map(([state, color]) => (
          <div key={state} className="flex items-center gap-1.5 text-xs text-gray-400">
            <span className={clsx("h-2 w-2 rounded-full", color)} />
            {STATE_LABELS[state]}: {counts[state] || 0}
          </div>
        ))}
      </div>
    </div>
  );
}
