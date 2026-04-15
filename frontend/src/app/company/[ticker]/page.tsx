"use client";
import { useState } from "react";
import {
  getCompany,
  getBeliefs,
  getThesis,
  getSignalHistory,
  approvePosition,
  type Signal,
  type BeliefLayer,
} from "@/lib/api";
import { useFetch } from "@/lib/hooks";
import SignalRadar from "@/components/RadarChart";
import ConditionDots from "@/components/ConditionDots";
import clsx from "clsx";

const TABS = ["Signals", "Belief Stack", "Thesis", "Predictions", "History"];

const DIRECTION_COLORS: Record<string, string> = {
  STRONGLY_CONFIRMING: "text-emerald-400",
  CONFIRMING: "text-emerald-300",
  NEUTRAL: "text-gray-400",
  CONTRADICTING: "text-orange-400",
  STRONGLY_CONTRADICTING: "text-red-400",
};

export default function CompanyPage({ params }: { params: { ticker: string } }) {
  const ticker = params.ticker.toUpperCase();
  const [tab, setTab] = useState(0);

  const { data: company, loading } = useFetch(() => getCompany(ticker), [ticker]);
  const { data: beliefs } = useFetch(() => getBeliefs(ticker), [ticker]);
  const { data: thesis } = useFetch(
    () => (company?.system_state === "NADIR_COMPLETE" ? getThesis(ticker) : Promise.resolve(null)),
    [ticker, company?.system_state]
  );

  if (loading) return <div className="text-gray-500">Loading {ticker}...</div>;
  if (!company) return <div className="text-gray-500">Company not found</div>;

  const signals = company.signals || [];
  const latestSignals = new Map<string, Signal>();
  for (const s of signals) {
    if (!latestSignals.has(s.signal_type)) latestSignals.set(s.signal_type, s);
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">{company.ticker}</h1>
          <p className="text-sm text-gray-400">{company.name} — {company.sector}</p>
        </div>
        <div className="flex items-center gap-4">
          <ConditionDots met={company.conditions_met} />
          <span className={clsx("badge text-sm", {
            "badge-critical": company.system_state === "NADIR_COMPLETE",
            "badge-medium": company.system_state === "WATCH",
            "badge-success": company.system_state === "ZENITH",
            "badge-low": company.system_state === "NORMAL",
          })}>
            {company.system_state.replace("_", " ")}
          </span>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-nadir-border">
        {TABS.map((t, i) => (
          <button
            key={t}
            onClick={() => setTab(i)}
            className={clsx(
              "px-4 py-2.5 text-sm font-medium transition-colors",
              tab === i
                ? "border-b-2 border-nadir-accent text-nadir-accent"
                : "text-gray-400 hover:text-gray-200"
            )}
          >
            {t}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {tab === 0 && <SignalsTab signals={[...latestSignals.values()]} />}
      {tab === 1 && <BeliefTab beliefs={beliefs || []} />}
      {tab === 2 && <ThesisTab thesis={thesis} ticker={ticker} company={company} />}
      {tab === 3 && <PredictionsTab companyId={company.id} />}
      {tab === 4 && <HistoryTab signals={signals} alerts={company.alerts || []} />}
    </div>
  );
}

function SignalsTab({ signals }: { signals: Signal[] }) {
  const SIGNAL_NAMES: Record<string, string> = {
    SHORT_INTEREST: "Short Interest",
    ANALYST_SENTIMENT: "Analyst Sentiment",
    INSIDER_BUYING: "Insider Buying",
    GRR_STABILITY: "GRR Stability",
    MORAL_LANGUAGE: "Moral Language",
  };

  return (
    <div className="space-y-6">
      <div className="card flex justify-center">
        <SignalRadar signals={signals} />
      </div>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        {signals.map((s) => (
          <div key={s.id} className={clsx("card border-l-4", s.condition_met ? "border-l-red-500" : "border-l-gray-700")}>
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-semibold">{SIGNAL_NAMES[s.signal_type] || s.signal_type}</h3>
              <span className={clsx("badge", s.condition_met ? "badge-critical" : "badge-low")}>
                {s.condition_met ? "MET" : "NOT MET"}
              </span>
            </div>
            <p className="text-2xl font-bold tabular-nums text-gray-200">
              {s.current_value != null ? Number(s.current_value).toFixed(4) : "—"}
            </p>
            <p className="text-xs text-gray-500 mt-1">
              Threshold: {s.threshold != null ? Number(s.threshold).toFixed(4) : "—"}
            </p>
            <p className="text-xs text-gray-500">
              Source: {s.source || "—"} | Updated: {new Date(s.last_updated).toLocaleString()}
            </p>
            {s.raw_data && (
              <details className="mt-2">
                <summary className="cursor-pointer text-xs text-gray-500 hover:text-gray-300">Raw data</summary>
                <pre className="mt-1 max-h-40 overflow-y-auto rounded bg-gray-900 p-2 text-[10px] text-gray-400">
                  {JSON.stringify(s.raw_data, null, 2)}
                </pre>
              </details>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function BeliefTab({ beliefs }: { beliefs: BeliefLayer[] }) {
  const LAYER_ORDER = ["SURFACE", "FINANCIAL", "STRUCTURAL", "AXIOM"];
  const sorted = [...beliefs].sort(
    (a, b) => LAYER_ORDER.indexOf(a.layer) - LAYER_ORDER.indexOf(b.layer)
  );

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
      {sorted.map((b) => {
        const isWeakest = b.net_direction === "STRONGLY_CONTRADICTING";
        return (
          <div key={b.id} className={clsx("card", isWeakest && "ring-2 ring-red-500/50")}>
            {isWeakest && (
              <p className="mb-2 text-xs font-bold uppercase tracking-wider text-red-400">
                Weakest Node
              </p>
            )}
            <h3 className="text-sm font-bold uppercase tracking-wider text-gray-300">{b.layer}</h3>
            <p className="mt-2 text-sm text-gray-300">{b.assumption_text}</p>
            <div className="mt-3 space-y-1 text-xs">
              <p className="text-gray-500">Market implied: <span className="text-gray-300">{b.market_implied_value}</span></p>
              <p className={DIRECTION_COLORS[b.net_direction] || "text-gray-400"}>
                Direction: {b.net_direction.replace("_", " ")}
              </p>
              <p className="text-gray-500">
                Confirming: {b.confirming_signals} | Contradicting: {b.contradicting_signals}
              </p>
            </div>
          </div>
        );
      })}
      {beliefs.length === 0 && <p className="text-sm text-gray-500 col-span-2">No belief stack built yet. Company must reach WATCH state (3+ conditions).</p>}
    </div>
  );
}

function ThesisTab({ thesis, ticker, company }: { thesis: any; ticker: string; company: any }) {
  if (!thesis) {
    return <p className="text-sm text-gray-500">No thesis generated yet. Company must reach NADIR_COMPLETE with validation.</p>;
  }

  const pendingPosition = company.positions?.find((p: any) => p.pending_approval);

  return (
    <div className="space-y-4">
      {pendingPosition && (
        <div className="card border-2 border-red-500/50 bg-red-950/20">
          <p className="text-sm font-bold text-red-300 mb-2">Trade Pending Approval</p>
          <p className="text-sm text-gray-300">
            {pendingPosition.shares} shares @ ${Number(pendingPosition.entry_price).toFixed(2)} = ${Number(pendingPosition.dollar_amount).toLocaleString()}
          </p>
          <button
            onClick={async () => { await approvePosition(ticker); window.location.reload(); }}
            className="btn-danger mt-3"
          >
            Approve Trade
          </button>
        </div>
      )}

      <Field label="Narrative (Market Believes)" value={thesis.narrative} />
      <Field label="Reality (Signals Show)" value={thesis.reality} />
      <Field label="Disconnect" value={thesis.disconnect} />
      <Field label="Rehabilitation Mechanism" value={thesis.rehabilitation_mechanism} />
      <Field label="Timeline" value={thesis.rehabilitation_timeline} />
      <Field label="Falsification Condition" value={thesis.falsification_condition} accent="red" />
      <Field label="Variant View" value={thesis.variant_view_summary} />
      {thesis.key_risks && (
        <div className="card">
          <p className="text-xs font-semibold uppercase tracking-wider text-gray-400 mb-2">Key Risks</p>
          <ul className="list-disc pl-4 space-y-1 text-sm text-gray-300">
            {thesis.key_risks.map((r: string, i: number) => <li key={i}>{r}</li>)}
          </ul>
        </div>
      )}
    </div>
  );
}

function Field({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div className="card">
      <p className="text-xs font-semibold uppercase tracking-wider text-gray-400 mb-1">{label}</p>
      <p className={clsx("text-sm", accent === "red" ? "text-red-300" : "text-gray-300")}>{value}</p>
    </div>
  );
}

function PredictionsTab({ companyId }: { companyId: string }) {
  return <p className="text-sm text-gray-500">Predictions for this company will appear here. Create predictions from the Predictions page.</p>;
}

function HistoryTab({ signals, alerts }: { signals: Signal[]; alerts: any[] }) {
  const events = [
    ...signals.map((s) => ({ time: s.last_updated, type: "signal", label: `${s.signal_type}: ${s.current_value} (${s.condition_met ? "MET" : "not met"})` })),
    ...alerts.map((a: any) => ({ time: a.created_at, type: "alert", label: `[${a.priority}] ${a.alert_text}` })),
  ].sort((a, b) => new Date(b.time).getTime() - new Date(a.time).getTime());

  return (
    <div className="card max-h-[600px] overflow-y-auto">
      {events.length === 0 ? (
        <p className="text-sm text-gray-500">No history yet</p>
      ) : (
        <div className="space-y-2">
          {events.slice(0, 100).map((e, i) => (
            <div key={i} className="flex items-start gap-3 text-sm">
              <span className="shrink-0 text-xs text-gray-500 tabular-nums w-36">
                {new Date(e.time).toLocaleString()}
              </span>
              <span className={clsx("badge shrink-0", e.type === "alert" ? "badge-high" : "badge-low")}>
                {e.type}
              </span>
              <span className="text-gray-300">{e.label}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
