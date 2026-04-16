"use client";
import { useState } from "react";
import { exitPosition, getPositionHistory, getPositions, type Position } from "@/lib/api";
import { useFetch, useInterval } from "@/lib/hooks";
import Link from "next/link";
import clsx from "clsx";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
  PieChart, Pie, Cell,
} from "recharts";

const STATUS_COLORS: Record<string, string> = {
  OPEN: "badge-success",
  CLOSED_PROFIT: "bg-emerald-900/50 text-emerald-300",
  CLOSED_LOSS: "bg-red-900/50 text-red-300",
  CLOSED_TIMEOUT: "bg-gray-800 text-gray-400",
  CLOSED_FALSIFIED: "bg-purple-900/50 text-purple-300",
};

export default function PositionsPage() {
  const { data: openPositions, reload } = useFetch(() => getPositions(), []);
  const { data: closedPositions } = useFetch(() => getPositionHistory(), []);
  const [exiting, setExiting] = useState<string | null>(null);

  useInterval(reload, 30000);

  const handleExit = async (ticker: string) => {
    setExiting(ticker);
    try {
      await exitPosition(ticker, "MANUAL");
      reload();
    } catch (e) { console.error(e); }
    setExiting(null);
  };

  const wins = (closedPositions || []).filter((p) => p.return_pct && Number(p.return_pct) > 0);
  const losses = (closedPositions || []).filter((p) => p.return_pct && Number(p.return_pct) <= 0);
  const pieData = [
    { name: "Wins", value: wins.length, color: "#10b981" },
    { name: "Losses", value: losses.length, color: "#ef4444" },
  ];

  // Equity curve
  const equityCurve: { date: string; cumReturn: number }[] = [];
  let cum = 0;
  for (const p of [...(closedPositions || [])].sort(
    (a, b) => new Date(a.exit_date || 0).getTime() - new Date(b.exit_date || 0).getTime()
  )) {
    if (p.return_pct && p.exit_date) {
      cum += Number(p.return_pct) * Number(p.position_pct);
      equityCurve.push({ date: new Date(p.exit_date).toLocaleDateString(), cumReturn: +(cum * 100).toFixed(2) });
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold tracking-tight">Positions</h1>

      {/* Open Positions */}
      <div className="card overflow-x-auto p-0">
        <div className="px-5 pt-5 pb-3">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-gray-400">Open Positions</h2>
        </div>
        <table className="w-full">
          <thead>
            <tr>
              <th className="table-header">Ticker</th>
              <th className="table-header">Entry</th>
              <th className="table-header">Shares</th>
              <th className="table-header">Size</th>
              <th className="table-header">Days</th>
              <th className="table-header">P(Win)</th>
              <th className="table-header">Kelly</th>
              <th className="table-header">GRR</th>
              <th className="table-header">Status</th>
              <th className="table-header">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-nadir-border">
            {(openPositions || []).map((p) => (
              <tr key={p.id} className="hover:bg-gray-800/50">
                <td className="table-cell">
                  <Link href={`/company/${p.ticker}`} className="font-medium text-nadir-accent hover:underline">{p.ticker}</Link>
                </td>
                <td className="table-cell tabular-nums">${Number(p.entry_price).toFixed(2)}</td>
                <td className="table-cell tabular-nums">{p.shares}</td>
                <td className="table-cell tabular-nums">${Number(p.dollar_amount).toLocaleString()}</td>
                <td className="table-cell tabular-nums">
                  {Math.floor((Date.now() - new Date(p.entry_date).getTime()) / 86400000)}
                </td>
                <td className="table-cell tabular-nums">{p.p_win ? `${(Number(p.p_win) * 100).toFixed(0)}%` : "—"}</td>
                <td className="table-cell tabular-nums">{p.kelly_fraction ? `${(Number(p.kelly_fraction) * 100).toFixed(1)}%` : "—"}</td>
                <td className="table-cell text-xs tabular-nums">
                  {p.falsification_conditions?.grr_floor
                    ? <span className="text-gray-400">Floor: {(p.falsification_conditions.grr_floor * 100).toFixed(0)}%</span>
                    : "—"}
                </td>
                <td className="table-cell">
                  <span className={clsx("badge", p.pending_approval ? "badge-critical" : "badge-success")}>
                    {p.pending_approval ? "PENDING" : "OPEN"}
                  </span>
                </td>
                <td className="table-cell">
                  <button onClick={() => handleExit(p.ticker)} disabled={exiting === p.ticker} className="btn-danger text-xs py-1 px-2">
                    {exiting === p.ticker ? "..." : "Exit"}
                  </button>
                </td>
              </tr>
            ))}
            {!openPositions?.length && (
              <tr><td colSpan={10} className="table-cell text-center text-gray-500">No open positions</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Analytics */}
      {(closedPositions?.length || 0) > 0 && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <div className="card">
            <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-gray-400">Equity Curve</h3>
            <ResponsiveContainer width="100%" height={250}>
              <LineChart data={equityCurve}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                <XAxis dataKey="date" tick={{ fill: "#6b7280", fontSize: 10 }} />
                <YAxis tick={{ fill: "#6b7280", fontSize: 10 }} />
                <Tooltip contentStyle={{ background: "#111827", border: "1px solid #1f2937" }} />
                <Line type="monotone" dataKey="cumReturn" stroke="#3b82f6" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <div className="card flex flex-col items-center">
            <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-gray-400 self-start">Win Rate</h3>
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" innerRadius={60} outerRadius={90} paddingAngle={3}>
                  {pieData.map((d) => <Cell key={d.name} fill={d.color} />)}
                </Pie>
                <Tooltip contentStyle={{ background: "#111827", border: "1px solid #1f2937" }} />
              </PieChart>
            </ResponsiveContainer>
            <p className="text-sm text-gray-400">
              {wins.length}W / {losses.length}L ({closedPositions?.length ? ((wins.length / closedPositions.length) * 100).toFixed(0) : 0}%)
            </p>
          </div>
        </div>
      )}

      {/* Closed Positions */}
      <div className="card overflow-x-auto p-0">
        <div className="px-5 pt-5 pb-3">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-gray-400">Closed Positions</h2>
        </div>
        <table className="w-full">
          <thead>
            <tr>
              <th className="table-header">Ticker</th>
              <th className="table-header">Entry</th>
              <th className="table-header">Exit</th>
              <th className="table-header">Return</th>
              <th className="table-header">Exit Reason</th>
              <th className="table-header">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-nadir-border">
            {(closedPositions || []).map((p) => {
              const ret = p.return_pct ? Number(p.return_pct) * 100 : 0;
              return (
                <tr key={p.id} className="hover:bg-gray-800/50">
                  <td className="table-cell font-medium">{p.ticker}</td>
                  <td className="table-cell tabular-nums">${Number(p.entry_price).toFixed(2)}</td>
                  <td className="table-cell tabular-nums">{p.exit_price ? `$${Number(p.exit_price).toFixed(2)}` : "—"}</td>
                  <td className={clsx("table-cell tabular-nums font-bold", ret >= 0 ? "text-emerald-400" : "text-red-400")}>
                    {ret >= 0 ? "+" : ""}{ret.toFixed(2)}%
                  </td>
                  <td className="table-cell text-gray-400">{p.exit_reason || "—"}</td>
                  <td className="table-cell">
                    <span className={clsx("badge", STATUS_COLORS[p.status] || "badge-low")}>{p.status.replace("CLOSED_", "")}</span>
                  </td>
                </tr>
              );
            })}
            {!closedPositions?.length && (
              <tr><td colSpan={6} className="table-cell text-center text-gray-500">No closed positions yet</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
