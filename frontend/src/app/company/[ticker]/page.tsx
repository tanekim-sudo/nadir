"use client";
import { useState } from "react";
import {
  getCompany,
  getBeliefStack,
  getThesis,
  approvePosition,
  type Signal,
  type BeliefNode,
  type BeliefStackSummary,
  type DCFData,
} from "@/lib/api";
import { useFetch } from "@/lib/hooks";
import SignalRadar from "@/components/RadarChart";
import ConditionDots from "@/components/ConditionDots";
import clsx from "clsx";

const TABS = ["Signals", "Belief Stack", "Thesis", "Predictions", "History"];

const DIRECTION_COLORS: Record<string, string> = {
  STRONGLY_BULLISH: "text-emerald-400",
  BULLISH: "text-emerald-300",
  NEUTRAL: "text-gray-400",
  BEARISH: "text-orange-400",
  STRONGLY_BEARISH: "text-red-400",
};

const CONFIDENCE_OPACITY: Record<string, string> = {
  HIGH: "opacity-100",
  MEDIUM: "opacity-70",
  LOW: "opacity-40",
};

export default function CompanyPage({ params }: { params: { ticker: string } }) {
  const ticker = params.ticker.toUpperCase();
  const [tab, setTab] = useState(0);

  const { data: company, loading } = useFetch(() => getCompany(ticker), [ticker]);
  const { data: beliefStack } = useFetch(() => getBeliefStack(ticker), [ticker]);
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

      {tab === 0 && <SignalsTab signals={[...latestSignals.values()]} />}
      {tab === 1 && <BeliefTab beliefStack={beliefStack} />}
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
    JOB_POSTING_VELOCITY: "Customer Job Posting Velocity",
    SQUEEZE_PROBABILITY: "Short Squeeze Probability",
    GRR_MONITORING: "GRR (Post-Entry Monitoring)",
  };

  const SIGNAL_DESC: Record<string, string> = {
    SHORT_INTEREST: ">20% of float + top quintile borrow rate",
    ANALYST_SENTIMENT: ">70% sell ratings",
    INSIDER_BUYING: "Composite score >8.0",
    JOB_POSTING_VELOCITY: "Velocity > -0.10 (customers still hiring)",
    SQUEEZE_PROBABILITY: "Squeeze score > 0.65",
    GRR_MONITORING: "Falsification threshold (post-entry only)",
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
              {SIGNAL_DESC[s.signal_type] || `Threshold: ${s.threshold}`}
            </p>
            <p className="text-xs text-gray-500">
              Source: {s.source || "—"} | {new Date(s.last_updated).toLocaleString()}
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

function BeliefTab({ beliefStack }: { beliefStack: BeliefStackSummary | null | undefined }) {
  const [selectedNode, setSelectedNode] = useState<string | null>(null);

  if (!beliefStack || !beliefStack.nodes.length) {
    return <p className="text-sm text-gray-500">No belief stack built yet. Company must reach WATCH state (3+ conditions).</p>;
  }

  const { nodes, dcf, primary_mispricing_node, primary_conviction } = beliefStack;
  const rootNodes = nodes.filter(n => !n.parent_node);
  const leafNodes = nodes.filter(n => n.parent_node);
  const selected = nodes.find(n => n.node_id === selectedNode);

  const directionBg = (dir: string) => {
    if (dir.includes("BULLISH")) return "bg-emerald-900/30 border-emerald-500/50";
    if (dir.includes("BEARISH")) return "bg-red-900/30 border-red-500/50";
    return "bg-gray-800/50 border-gray-600/50";
  };

  return (
    <div className="space-y-6">
      {/* DCF Summary Bar */}
      {dcf && (
        <div className="card grid grid-cols-2 gap-4 md:grid-cols-4">
          <div>
            <p className="text-xs text-gray-500 uppercase">Implied EV</p>
            <p className="text-lg font-bold text-gray-200">${(dcf.current_ev || 0).toLocaleString()}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500 uppercase">Implied Y1 Growth</p>
            <p className="text-lg font-bold text-gray-200">{dcf.implied_year1_growth != null ? `${(Number(dcf.implied_year1_growth) * 100).toFixed(1)}%` : "—"}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500 uppercase">Implied Terminal Margin</p>
            <p className="text-lg font-bold text-gray-200">{dcf.implied_terminal_margin != null ? `${(Number(dcf.implied_terminal_margin) * 100).toFixed(1)}%` : "—"}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500 uppercase">Primary Driver</p>
            <p className="text-lg font-bold text-nadir-accent">
              {primary_mispricing_node || "—"}{" "}
              {primary_conviction != null && <span className="text-sm text-gray-400">({primary_conviction.toFixed(2)})</span>}
            </p>
          </div>
        </div>
      )}

      {/* Tree Visualization */}
      <div className="card overflow-x-auto">
        <p className="mb-4 text-xs font-semibold uppercase tracking-wider text-gray-400">DCF Decomposition Tree</p>

        {/* Root level: EV */}
        <div className="flex flex-col items-center">
          <div className="rounded-lg border border-nadir-accent/50 bg-nadir-accent/10 px-6 py-3 text-center">
            <p className="text-xs text-gray-400">Current EV</p>
            <p className="text-xl font-bold text-nadir-accent">${(dcf?.current_ev || 0).toLocaleString()}</p>
            <p className="text-xs text-gray-500">EV/Rev: {dcf?.ev_revenue_multiple ? Number(dcf.ev_revenue_multiple).toFixed(1) : "—"}x</p>
          </div>

          <div className="h-8 w-px bg-gray-700" />

          {/* Level 1: A, B, C */}
          <div className="flex gap-6 flex-wrap justify-center">
            {rootNodes.map((root) => {
              const children = leafNodes.filter(n => n.parent_node === root.node_id);
              const isPrimary = children.some(c => c.node_id === primary_mispricing_node);
              return (
                <div key={root.node_id} className="flex flex-col items-center">
                  <div className={clsx(
                    "rounded-lg border px-5 py-3 text-center min-w-[180px] cursor-pointer transition-all",
                    isPrimary ? "border-nadir-accent ring-2 ring-nadir-accent/30" : "border-gray-700",
                    "hover:border-gray-500 bg-gray-800/50"
                  )} onClick={() => setSelectedNode(root.node_id === selectedNode ? null : root.node_id)}>
                    <p className="text-[10px] font-bold text-gray-500 uppercase">{root.node_id}</p>
                    <p className="text-sm font-semibold text-gray-200">{root.node_name}</p>
                    <p className="text-lg font-bold text-gray-100 mt-1">{root.market_implied_value || "—"}</p>
                  </div>

                  <div className="h-6 w-px bg-gray-700" />

                  {/* Level 2: leaf nodes */}
                  <div className="flex gap-3 flex-wrap justify-center">
                    {children.map((leaf) => {
                      const isPrimaryLeaf = leaf.node_id === primary_mispricing_node;
                      return (
                        <div
                          key={leaf.node_id}
                          onClick={() => setSelectedNode(leaf.node_id === selectedNode ? null : leaf.node_id)}
                          className={clsx(
                            "rounded-lg border px-3 py-2 text-center cursor-pointer transition-all min-w-[140px]",
                            directionBg(leaf.evidence_direction),
                            CONFIDENCE_OPACITY[leaf.evidence_confidence] || "opacity-40",
                            isPrimaryLeaf && "ring-2 ring-nadir-accent animate-pulse",
                            "hover:scale-105"
                          )}
                        >
                          <p className="text-[10px] font-bold text-gray-400">{leaf.node_id}</p>
                          <p className="text-xs font-medium text-gray-200 leading-tight">{leaf.node_name}</p>
                          <p className={clsx("text-xs mt-1 font-semibold", DIRECTION_COLORS[leaf.evidence_direction] || "text-gray-400")}>
                            {leaf.evidence_direction?.replace(/_/g, " ")}
                          </p>
                          {leaf.conviction_score != null && (
                            <p className="text-[10px] text-gray-500 mt-0.5">
                              conv: {Number(leaf.conviction_score).toFixed(2)}
                            </p>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Side Panel — selected node details */}
      {selected && (
        <div className="card border-l-4 border-l-nadir-accent">
          <div className="flex items-center justify-between mb-3">
            <div>
              <p className="text-xs font-bold text-gray-400 uppercase">{selected.node_id} — {selected.node_name}</p>
              {selected.node_id === primary_mispricing_node && (
                <span className="badge badge-critical text-xs mt-1">Primary Mispricing</span>
              )}
            </div>
            <button onClick={() => setSelectedNode(null)} className="text-gray-500 hover:text-gray-300 text-xl">&times;</button>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-xs text-gray-500">Market Implied</p>
              <p className="text-sm text-gray-200">{selected.market_implied_value || "—"}</p>
              <p className="text-xs text-gray-500 mt-0.5">{selected.market_implied_label}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500">Evidence Suggests</p>
              <p className="text-sm text-gray-200">{selected.evidence_value || "—"}</p>
              <p className="text-xs text-gray-500 mt-0.5">{selected.evidence_label}</p>
            </div>
          </div>

          <div className="mt-4 grid grid-cols-3 gap-4">
            <div>
              <p className="text-xs text-gray-500">Direction</p>
              <p className={clsx("text-sm font-semibold", DIRECTION_COLORS[selected.evidence_direction])}>
                {selected.evidence_direction?.replace(/_/g, " ")}
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-500">Confidence</p>
              <p className="text-sm text-gray-200">{selected.evidence_confidence}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500">Gap Magnitude</p>
              <p className="text-sm text-gray-200">{selected.gap_magnitude != null ? Number(selected.gap_magnitude).toFixed(4) : "—"}</p>
            </div>
          </div>

          {selected.evidence_sources && (
            <div className="mt-4">
              <p className="text-xs text-gray-500 mb-1">Evidence Sources</p>
              <div className="flex flex-wrap gap-1">
                {(Array.isArray(selected.evidence_sources) ? selected.evidence_sources : Object.values(selected.evidence_sources)).map((src: string, i: number) => (
                  <span key={i} className="badge badge-low text-xs">{src}</span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
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
      {thesis.quantitative_mispricing && (
        <Field label="Quantitative Mispricing (DCF)" value={thesis.quantitative_mispricing} accent="blue" />
      )}
      <Field label="Rehabilitation Mechanism" value={thesis.rehabilitation_mechanism} />
      <Field label="Timeline" value={thesis.rehabilitation_timeline} />
      <Field label="Falsification Condition" value={thesis.falsification_condition} accent="red" />
      {thesis.grr_falsification_threshold && (
        <Field label="GRR Falsification Threshold" value={`Auto-exit if GRR falls below ${(thesis.grr_falsification_threshold * 100).toFixed(0)}%`} accent="red" />
      )}
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
  const colorClass = accent === "red" ? "text-red-300" : accent === "blue" ? "text-blue-300" : "text-gray-300";
  return (
    <div className="card">
      <p className="text-xs font-semibold uppercase tracking-wider text-gray-400 mb-1">{label}</p>
      <p className={clsx("text-sm", colorClass)}>{value}</p>
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
