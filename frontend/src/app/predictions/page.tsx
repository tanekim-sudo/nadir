"use client";
import { useState } from "react";
import { createPrediction, getAccuracyStats, getPredictions, resolvePrediction, type Prediction } from "@/lib/api";
import { useFetch } from "@/lib/hooks";
import clsx from "clsx";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { formatDistanceToNow } from "date-fns";

export default function PredictionsPage() {
  const { data: predictions, reload } = useFetch(() => getPredictions(), []);
  const { data: accuracy } = useFetch(() => getAccuracyStats(), []);
  const [showForm, setShowForm] = useState(false);

  const active = (predictions || []).filter((p) => !p.resolved_at);
  const resolved = (predictions || []).filter((p) => p.resolved_at);

  const calData = accuracy?.by_confidence_bucket
    ? Object.entries(accuracy.by_confidence_bucket as Record<string, any>).map(([label, b]: [string, any]) => ({
        bucket: label,
        predicted: b.predicted_avg,
        actual: b.actual_rate * 100,
      }))
    : [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold tracking-tight">Predictions</h1>
        <button onClick={() => setShowForm(!showForm)} className="btn-primary">
          {showForm ? "Cancel" : "New Prediction"}
        </button>
      </div>

      {showForm && <PredictionForm onCreated={() => { setShowForm(false); reload(); }} />}

      {/* Accuracy overview */}
      {accuracy && (accuracy as any).total_resolved > 0 && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <div className="card text-center">
            <p className="text-xs uppercase tracking-wider text-gray-400">Accuracy</p>
            <p className="text-3xl font-bold text-nadir-accent">{(accuracy as any).accuracy_pct}%</p>
          </div>
          <div className="card text-center">
            <p className="text-xs uppercase tracking-wider text-gray-400">Confirmed</p>
            <p className="text-3xl font-bold text-emerald-400">{(accuracy as any).confirmed}</p>
          </div>
          <div className="card text-center">
            <p className="text-xs uppercase tracking-wider text-gray-400">Denied</p>
            <p className="text-3xl font-bold text-red-400">{(accuracy as any).denied}</p>
          </div>
        </div>
      )}

      {calData.length > 0 && (
        <div className="card">
          <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-gray-400">Calibration</h3>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={calData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
              <XAxis dataKey="bucket" tick={{ fill: "#6b7280", fontSize: 10 }} />
              <YAxis tick={{ fill: "#6b7280", fontSize: 10 }} />
              <Tooltip contentStyle={{ background: "#111827", border: "1px solid #1f2937" }} />
              <Bar dataKey="predicted" name="Predicted %" fill="#3b82f6" radius={[4, 4, 0, 0]} />
              <Bar dataKey="actual" name="Actual %" fill="#10b981" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Active predictions */}
      <div className="card">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-gray-400">Active ({active.length})</h2>
        <div className="space-y-2">
          {active.map((p) => {
            const daysLeft = Math.ceil((new Date(p.resolution_date).getTime() - Date.now()) / 86400000);
            return (
              <div key={p.id} className="rounded-lg bg-gray-800/40 p-3">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-sm text-gray-200">{p.claim_text}</p>
                    <p className="mt-1 text-xs text-gray-500">Outcome: {p.observable_outcome}</p>
                    <p className="text-xs text-gray-500">
                      Confidence: {Number(p.confidence_pct).toFixed(0)}% | Resolves in {daysLeft > 0 ? `${daysLeft}d` : "OVERDUE"}
                    </p>
                  </div>
                  <ResolveButtons predictionId={p.id} onResolved={reload} />
                </div>
              </div>
            );
          })}
          {active.length === 0 && <p className="text-sm text-gray-500">No active predictions</p>}
        </div>
      </div>

      {/* Resolved */}
      <div className="card">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-gray-400">Resolved ({resolved.length})</h2>
        <div className="space-y-2">
          {resolved.map((p) => (
            <div key={p.id} className={clsx("rounded-lg p-3 border-l-4", {
              "border-l-emerald-500 bg-emerald-950/10": p.outcome_direction === "CONFIRMED",
              "border-l-red-500 bg-red-950/10": p.outcome_direction === "DENIED",
              "border-l-gray-600": p.outcome_direction === "AMBIGUOUS",
            })}>
              <p className="text-sm text-gray-200">{p.claim_text}</p>
              <p className="mt-1 text-xs text-gray-500">
                {p.outcome_direction} — {p.actual_outcome}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function PredictionForm({ onCreated }: { onCreated: () => void }) {
  const [companyId, setCompanyId] = useState("");
  const [claim, setClaim] = useState("");
  const [outcome, setOutcome] = useState("");
  const [date, setDate] = useState("");
  const [confidence, setConfidence] = useState(50);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await createPrediction({
      company_id: companyId, claim_text: claim, observable_outcome: outcome,
      resolution_date: date, confidence_pct: confidence,
    });
    onCreated();
  };

  return (
    <form onSubmit={handleSubmit} className="card space-y-4">
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <div>
          <label className="mb-1 block text-xs text-gray-400">Company ID (UUID)</label>
          <input value={companyId} onChange={(e) => setCompanyId(e.target.value)} required className="w-full rounded-lg border border-nadir-border bg-gray-900 px-3 py-2 text-sm text-gray-200" />
        </div>
        <div>
          <label className="mb-1 block text-xs text-gray-400">Resolution Date</label>
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)} required className="w-full rounded-lg border border-nadir-border bg-gray-900 px-3 py-2 text-sm text-gray-200" />
        </div>
      </div>
      <div>
        <label className="mb-1 block text-xs text-gray-400">Claim</label>
        <textarea value={claim} onChange={(e) => setClaim(e.target.value)} required rows={2} className="w-full rounded-lg border border-nadir-border bg-gray-900 px-3 py-2 text-sm text-gray-200" />
      </div>
      <div>
        <label className="mb-1 block text-xs text-gray-400">Observable Outcome</label>
        <textarea value={outcome} onChange={(e) => setOutcome(e.target.value)} required rows={2} className="w-full rounded-lg border border-nadir-border bg-gray-900 px-3 py-2 text-sm text-gray-200" />
      </div>
      <div>
        <label className="mb-1 block text-xs text-gray-400">Confidence: {confidence}%</label>
        <input type="range" min="10" max="95" value={confidence} onChange={(e) => setConfidence(Number(e.target.value))} className="w-full" />
      </div>
      <button type="submit" className="btn-primary">Create Prediction</button>
    </form>
  );
}

function ResolveButtons({ predictionId, onResolved }: { predictionId: string; onResolved: () => void }) {
  const resolve = async (direction: string) => {
    const outcome = prompt("Describe the actual outcome:");
    if (!outcome) return;
    await resolvePrediction(predictionId, { actual_outcome: outcome, outcome_direction: direction });
    onResolved();
  };
  return (
    <div className="flex gap-1 shrink-0">
      <button onClick={() => resolve("CONFIRMED")} className="badge-success cursor-pointer text-[10px]">Confirm</button>
      <button onClick={() => resolve("DENIED")} className="badge-critical cursor-pointer text-[10px]">Deny</button>
      <button onClick={() => resolve("AMBIGUOUS")} className="badge-low cursor-pointer text-[10px]">Ambig</button>
    </div>
  );
}
