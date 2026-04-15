"use client";
import { useCallback, useState } from "react";
import { type Alert, approvePosition, getAlerts, reviewAlert } from "@/lib/api";
import { useFetch, useInterval, useSSE } from "@/lib/hooks";
import clsx from "clsx";
import { formatDistanceToNow } from "date-fns";

const PRIORITY_CLASS: Record<string, string> = {
  CRITICAL: "border-l-red-500 bg-red-950/30",
  HIGH: "border-l-orange-500 bg-orange-950/20",
  MEDIUM: "border-l-yellow-500 bg-yellow-950/15",
  LOW: "border-l-gray-600",
};

export default function AlertFeed() {
  const { data: alerts, reload } = useFetch(() => getAlerts(false), []);
  const [approving, setApproving] = useState<string | null>(null);

  useInterval(reload, 15000);

  const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  useSSE(`${API}/api/alerts/stream`, () => reload());

  const handleApprove = useCallback(
    async (alert: Alert) => {
      setApproving(alert.id);
      try {
        await approvePosition(alert.alert_text.split(" ")[0]?.replace(":", "").trim() || "");
        await reviewAlert(alert.id, "Trade approved");
        reload();
      } catch (e: any) {
        console.error(e);
      }
      setApproving(null);
    },
    [reload]
  );

  const handleDismiss = useCallback(
    async (alert: Alert) => {
      await reviewAlert(alert.id, "Dismissed");
      reload();
    },
    [reload]
  );

  if (!alerts?.length) {
    return (
      <div className="card">
        <p className="text-xs font-semibold uppercase tracking-wider text-gray-400 mb-3">Live Alerts</p>
        <p className="text-sm text-gray-500">No unreviewed alerts</p>
      </div>
    );
  }

  return (
    <div className="card max-h-96 overflow-y-auto">
      <p className="text-xs font-semibold uppercase tracking-wider text-gray-400 mb-3">
        Live Alerts ({alerts.length})
      </p>
      <div className="space-y-2">
        {alerts.map((a) => (
          <div
            key={a.id}
            className={clsx(
              "rounded-lg border-l-4 p-3 transition-colors",
              PRIORITY_CLASS[a.priority] || "border-l-gray-600"
            )}
          >
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <span className={clsx("badge", {
                    "badge-critical": a.priority === "CRITICAL",
                    "badge-high": a.priority === "HIGH",
                    "badge-medium": a.priority === "MEDIUM",
                    "badge-low": a.priority === "LOW",
                  })}>
                    {a.priority}
                  </span>
                  <span className="text-[10px] text-gray-500">
                    {formatDistanceToNow(new Date(a.created_at), { addSuffix: true })}
                  </span>
                </div>
                <p className="text-sm text-gray-300">{a.alert_text}</p>
              </div>
              <div className="flex shrink-0 gap-1.5">
                {a.alert_type === "APPROVAL_REQUIRED" && (
                  <button
                    onClick={() => handleApprove(a)}
                    disabled={approving === a.id}
                    className="btn-primary text-xs px-3 py-1"
                  >
                    {approving === a.id ? "..." : "Approve"}
                  </button>
                )}
                <button onClick={() => handleDismiss(a)} className="btn-ghost text-xs px-2 py-1">
                  ✓
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
