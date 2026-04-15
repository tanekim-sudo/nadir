"use client";
import { getKellyCalibration, getPerformance, getSignalAccuracy } from "@/lib/api";
import { useFetch } from "@/lib/hooks";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
  ScatterChart, Scatter, ZAxis,
  Cell,
} from "recharts";

export default function AnalyticsPage() {
  const { data: performance } = useFetch(() => getPerformance(), []);
  const { data: signalAcc } = useFetch(() => getSignalAccuracy(), []);
  const { data: kelly } = useFetch(() => getKellyCalibration(), []);

  const perf = performance as any;
  const kellyData = kelly as any;

  const signalBarData = ((signalAcc || []) as any[]).map((s: any) => ({
    signal: s.signal_type.replace("_", " ").substring(0, 12),
    precision: s.precision ? +(s.precision * 100).toFixed(1) : 0,
    recall: s.recall ? +(s.recall * 100).toFixed(1) : 0,
    f1: s.f1_score ? +(s.f1_score * 100).toFixed(1) : 0,
  }));

  const kellyScatter = kellyData?.buckets
    ? Object.values(kellyData.buckets as Record<string, any>).map((b: any) => ({
        predicted: b.predicted_avg,
        actual: b.actual_win_rate,
        count: b.count,
      }))
    : [];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold tracking-tight">Analytics</h1>

      {/* Performance KPIs */}
      {perf && (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <KPI label="Win Rate" value={`${perf.win_rate}%`} />
          <KPI label="Avg Return" value={`${perf.avg_return_pct}%`} />
          <KPI label="Avg Win" value={`+${perf.avg_win_pct}%`} accent="green" />
          <KPI label="Avg Loss" value={`${perf.avg_loss_pct}%`} accent="red" />
          <KPI label="Avg Hold (days)" value={perf.avg_holding_days || "—"} />
          <KPI label="False Positive Rate" value={`${perf.false_positive_rate}%`} accent="red" />
          <KPI label="Total Positions" value={perf.total_positions} />
          <KPI label="Open" value={perf.open_positions} />
        </div>
      )}

      {/* Signal accuracy */}
      <div className="card">
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-gray-400">
          Signal Performance
        </h2>
        {signalBarData.length > 0 ? (
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={signalBarData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
              <XAxis dataKey="signal" tick={{ fill: "#6b7280", fontSize: 10 }} />
              <YAxis tick={{ fill: "#6b7280", fontSize: 10 }} />
              <Tooltip contentStyle={{ background: "#111827", border: "1px solid #1f2937" }} />
              <Bar dataKey="precision" name="Precision" fill="#3b82f6" radius={[4, 4, 0, 0]} />
              <Bar dataKey="recall" name="Recall" fill="#10b981" radius={[4, 4, 0, 0]} />
              <Bar dataKey="f1" name="F1" fill="#f59e0b" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <p className="text-sm text-gray-500">No signal accuracy data yet. Resolve predictions to populate.</p>
        )}
      </div>

      {/* Kelly calibration */}
      <div className="card">
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-gray-400">
          Kelly Calibration
        </h2>
        <p className="mb-2 text-xs text-gray-500">
          Predicted win probability vs actual win rate. Well-calibrated = points on diagonal.
        </p>
        {kellyScatter.length > 0 ? (
          <ResponsiveContainer width="100%" height={300}>
            <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
              <XAxis type="number" dataKey="predicted" name="Predicted %" domain={[30, 80]} tick={{ fill: "#6b7280", fontSize: 10 }} />
              <YAxis type="number" dataKey="actual" name="Actual %" domain={[0, 100]} tick={{ fill: "#6b7280", fontSize: 10 }} />
              <ZAxis type="number" dataKey="count" range={[50, 400]} />
              <Tooltip contentStyle={{ background: "#111827", border: "1px solid #1f2937" }} />
              <Scatter data={kellyScatter} fill="#3b82f6">
                {kellyScatter.map((_, i) => <Cell key={i} fill="#3b82f6" />)}
              </Scatter>
            </ScatterChart>
          </ResponsiveContainer>
        ) : (
          <p className="text-sm text-gray-500">No calibration data yet. Close positions to populate.</p>
        )}
        {kellyData && kellyData.is_well_calibrated !== undefined && (
          <p className={`mt-2 text-sm ${kellyData.is_well_calibrated ? "text-emerald-400" : "text-orange-400"}`}>
            {kellyData.is_well_calibrated ? "System is well-calibrated" : "System needs recalibration"}
          </p>
        )}
      </div>

      {/* Equity curve */}
      {perf?.equity_curve?.length > 0 && (
        <div className="card">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-gray-400">
            Cumulative Returns
          </h2>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={perf.equity_curve}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
              <XAxis dataKey="date" tick={{ fill: "#6b7280", fontSize: 10 }} />
              <YAxis tick={{ fill: "#6b7280", fontSize: 10 }} />
              <Tooltip contentStyle={{ background: "#111827", border: "1px solid #1f2937" }} />
              <Bar dataKey="cumulative_return" name="Cumulative %" fill="#3b82f6" radius={[4, 4, 0, 0]}>
                {perf.equity_curve.map((_: any, i: number) => (
                  <Cell key={i} fill={perf.equity_curve[i].cumulative_return >= 0 ? "#10b981" : "#ef4444"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}

function KPI({ label, value, accent }: { label: string; value: string | number; accent?: string }) {
  const colorClass = accent === "green" ? "text-emerald-400" : accent === "red" ? "text-red-400" : "text-gray-200";
  return (
    <div className="card text-center">
      <p className="text-[10px] uppercase tracking-wider text-gray-500">{label}</p>
      <p className={`mt-1 text-xl font-bold tabular-nums ${colorClass}`}>{value}</p>
    </div>
  );
}
