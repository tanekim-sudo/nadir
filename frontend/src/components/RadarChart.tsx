"use client";
import {
  Radar,
  RadarChart as RechartsRadar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
} from "recharts";
import type { Signal } from "@/lib/api";

const SIGNAL_ORDER = ["SHORT_INTEREST", "ANALYST_SENTIMENT", "INSIDER_BUYING", "GRR_STABILITY", "MORAL_LANGUAGE"];
const SIGNAL_SHORT = { SHORT_INTEREST: "Short Int.", ANALYST_SENTIMENT: "Analyst Sell", INSIDER_BUYING: "Insider Buy", GRR_STABILITY: "GRR", MORAL_LANGUAGE: "Moral Lang." };

export default function SignalRadar({ signals }: { signals: Signal[] }) {
  const signalMap = new Map(signals.map((s) => [s.signal_type, s]));

  const data = SIGNAL_ORDER.map((type) => {
    const s = signalMap.get(type);
    const value = s?.current_value ?? 0;
    const threshold = s?.threshold ? Number(s.threshold) : 1;
    const normalized = Math.min((Number(value) / threshold) * 100, 100);
    return {
      subject: (SIGNAL_SHORT as any)[type] || type,
      value: Math.round(normalized),
      met: s?.condition_met ? 100 : 0,
    };
  });

  return (
    <ResponsiveContainer width="100%" height={280}>
      <RechartsRadar cx="50%" cy="50%" outerRadius="70%" data={data}>
        <PolarGrid stroke="#1f2937" />
        <PolarAngleAxis dataKey="subject" tick={{ fill: "#9ca3af", fontSize: 11 }} />
        <PolarRadiusAxis angle={90} domain={[0, 100]} tick={false} axisLine={false} />
        <Radar name="Value" dataKey="value" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.25} strokeWidth={2} />
        <Radar name="Threshold Met" dataKey="met" stroke="#ef4444" fill="#ef4444" fillOpacity={0.1} strokeWidth={1} strokeDasharray="4 4" />
      </RechartsRadar>
    </ResponsiveContainer>
  );
}
