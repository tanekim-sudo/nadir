"use client";
import { getPositions, getUniverse, getWatchlist, getPredictions, type Company, type Position } from "@/lib/api";
import { useFetch, useInterval } from "@/lib/hooks";
import StatCard from "@/components/StatCard";
import StateBar from "@/components/StateBar";
import AlertFeed from "@/components/AlertFeed";
import ConditionDots from "@/components/ConditionDots";
import Link from "next/link";

export default function CommandCenter() {
  const { data: companies, reload: reloadCos } = useFetch(() => getUniverse(), []);
  const { data: positions, reload: reloadPos } = useFetch(() => getPositions(), []);
  const { data: predictions } = useFetch(() => getPredictions(true), []);

  useInterval(() => { reloadCos(); reloadPos(); }, 30000);

  const nadirCount = companies?.filter((c) => c.system_state === "NADIR_COMPLETE").length || 0;
  const topConditions = [...(companies || [])]
    .sort((a, b) => b.conditions_met - a.conditions_met)
    .slice(0, 10);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold tracking-tight">Command Center</h1>

      {/* Stat cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Universe Size" value={companies?.length || 0} accent="blue" sub="companies tracked" />
        <StatCard label="NADIR Complete" value={nadirCount} accent="red" badge={nadirCount} sub="all 5 conditions met" />
        <StatCard label="Open Positions" value={positions?.length || 0} accent="green" sub="active trades" />
        <StatCard label="Active Predictions" value={predictions?.length || 0} accent="yellow" sub="pending resolution" />
      </div>

      {/* State distribution */}
      {companies && <StateBar companies={companies} />}

      {/* Alert feed */}
      <AlertFeed />

      {/* Two-column bottom */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Top conditions */}
        <div className="card">
          <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-gray-400">
            Top 10 by Conditions Met
          </p>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr>
                  <th className="table-header">Ticker</th>
                  <th className="table-header">State</th>
                  <th className="table-header">Conditions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-nadir-border">
                {topConditions.map((c) => (
                  <tr key={c.id} className="hover:bg-gray-800/50 transition-colors">
                    <td className="table-cell">
                      <Link href={`/company/${c.ticker}`} className="font-medium text-nadir-accent hover:underline">
                        {c.ticker}
                      </Link>
                    </td>
                    <td className="table-cell">
                      <StateBadge state={c.system_state} />
                    </td>
                    <td className="table-cell">
                      <ConditionDots met={c.conditions_met} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Open positions P&L */}
        <div className="card">
          <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-gray-400">
            Open Positions
          </p>
          {!positions?.length ? (
            <p className="text-sm text-gray-500">No open positions</p>
          ) : (
            <div className="space-y-2">
              {positions.map((p) => {
                const pnl = p.return_pct ? Number(p.return_pct) * 100 : 0;
                return (
                  <div key={p.id} className="flex items-center justify-between rounded-lg bg-gray-800/40 px-4 py-2.5">
                    <div>
                      <Link href={`/company/${p.ticker}`} className="font-medium text-nadir-accent hover:underline">
                        {p.ticker}
                      </Link>
                      <p className="text-xs text-gray-500">
                        {p.shares} shares @ ${Number(p.entry_price).toFixed(2)}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className={`text-sm font-bold tabular-nums ${pnl >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                        {pnl >= 0 ? "+" : ""}{pnl.toFixed(2)}%
                      </p>
                      <p className="text-xs text-gray-500">
                        ${Number(p.dollar_amount).toLocaleString()}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function StateBadge({ state }: { state: string }) {
  const colors: Record<string, string> = {
    NORMAL: "bg-gray-800 text-gray-400",
    WATCH: "bg-yellow-900/50 text-yellow-300",
    NADIR_COMPLETE: "bg-red-900/50 text-red-300",
    ZENITH: "bg-emerald-900/50 text-emerald-300",
    CONSTRAINT_DISSOLVING: "bg-purple-900/50 text-purple-300",
  };
  return (
    <span className={`badge ${colors[state] || "bg-gray-800 text-gray-400"}`}>
      {state.replace("_", " ")}
    </span>
  );
}
