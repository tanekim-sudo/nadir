"use client";
import { useState } from "react";
import { addCompany, getUniverse, refreshSignals, type Company } from "@/lib/api";
import { useFetch } from "@/lib/hooks";
import ConditionDots from "@/components/ConditionDots";
import Link from "next/link";
import clsx from "clsx";

const STATE_COLORS: Record<string, string> = {
  NORMAL: "bg-gray-800 text-gray-400",
  WATCH: "bg-yellow-900/50 text-yellow-300",
  NADIR_COMPLETE: "bg-red-900/50 text-red-300",
  ZENITH: "bg-emerald-900/50 text-emerald-300",
  CONSTRAINT_DISSOLVING: "bg-purple-900/50 text-purple-300",
};

export default function UniversePage() {
  const { data: companies, reload } = useFetch(() => getUniverse(), []);
  const [search, setSearch] = useState("");
  const [stateFilter, setStateFilter] = useState("");
  const [minConditions, setMinConditions] = useState(0);
  const [newTicker, setNewTicker] = useState("");
  const [adding, setAdding] = useState(false);

  const filtered = (companies || []).filter((c) => {
    if (search && !c.ticker.toLowerCase().includes(search.toLowerCase()) && !c.name.toLowerCase().includes(search.toLowerCase())) return false;
    if (stateFilter && c.system_state !== stateFilter) return false;
    if (c.conditions_met < minConditions) return false;
    return true;
  });

  const handleAdd = async () => {
    if (!newTicker.trim()) return;
    setAdding(true);
    try {
      await addCompany({ ticker: newTicker.trim().toUpperCase() });
      setNewTicker("");
      reload();
    } catch (e) {
      console.error(e);
    }
    setAdding(false);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold tracking-tight">Universe</h1>
        <span className="text-sm text-gray-500">{filtered.length} companies</span>
      </div>

      {/* Filters */}
      <div className="card flex flex-wrap items-end gap-4">
        <div>
          <label className="mb-1 block text-xs text-gray-400">Search</label>
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Ticker or name..."
            className="rounded-lg border border-nadir-border bg-gray-900 px-3 py-2 text-sm text-gray-200 focus:border-nadir-accent focus:outline-none"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs text-gray-400">State</label>
          <select
            value={stateFilter}
            onChange={(e) => setStateFilter(e.target.value)}
            className="rounded-lg border border-nadir-border bg-gray-900 px-3 py-2 text-sm text-gray-200 focus:border-nadir-accent focus:outline-none"
          >
            <option value="">All States</option>
            <option value="NORMAL">Normal</option>
            <option value="WATCH">Watch</option>
            <option value="NADIR_COMPLETE">NADIR Complete</option>
            <option value="ZENITH">Zenith</option>
            <option value="CONSTRAINT_DISSOLVING">Dissolving</option>
          </select>
        </div>
        <div>
          <label className="mb-1 block text-xs text-gray-400">Min Conditions: {minConditions}</label>
          <input
            type="range"
            min="0"
            max="5"
            value={minConditions}
            onChange={(e) => setMinConditions(Number(e.target.value))}
            className="w-32"
          />
        </div>
        <div className="flex items-end gap-2">
          <div>
            <label className="mb-1 block text-xs text-gray-400">Add Ticker</label>
            <input
              value={newTicker}
              onChange={(e) => setNewTicker(e.target.value)}
              placeholder="TICKER"
              className="w-24 rounded-lg border border-nadir-border bg-gray-900 px-3 py-2 text-sm text-gray-200 uppercase focus:border-nadir-accent focus:outline-none"
              onKeyDown={(e) => e.key === "Enter" && handleAdd()}
            />
          </div>
          <button onClick={handleAdd} disabled={adding} className="btn-primary">
            {adding ? "..." : "Add"}
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="card overflow-x-auto p-0">
        <table className="w-full">
          <thead>
            <tr>
              <th className="table-header">Ticker</th>
              <th className="table-header">Name</th>
              <th className="table-header">State</th>
              <th className="table-header">Conditions</th>
              <th className="table-header">Last Scanned</th>
              <th className="table-header">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-nadir-border">
            {filtered.map((c) => (
              <tr key={c.id} className="hover:bg-gray-800/50 transition-colors">
                <td className="table-cell">
                  <Link href={`/company/${c.ticker}`} className="font-medium text-nadir-accent hover:underline">
                    {c.ticker}
                  </Link>
                </td>
                <td className="table-cell text-gray-400 max-w-[200px] truncate">{c.name}</td>
                <td className="table-cell">
                  <span className={clsx("badge", STATE_COLORS[c.system_state])}>
                    {c.system_state.replace("_", " ")}
                  </span>
                </td>
                <td className="table-cell">
                  <ConditionDots met={c.conditions_met} />
                </td>
                <td className="table-cell text-xs text-gray-500">
                  {c.last_scanned ? new Date(c.last_scanned).toLocaleDateString() : "Never"}
                </td>
                <td className="table-cell">
                  <button
                    onClick={async () => { await refreshSignals(c.ticker); reload(); }}
                    className="btn-ghost text-xs"
                  >
                    Refresh
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
