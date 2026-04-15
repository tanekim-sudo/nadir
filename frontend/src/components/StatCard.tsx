import clsx from "clsx";

interface StatCardProps {
  label: string;
  value: string | number;
  sub?: string;
  accent?: "blue" | "red" | "green" | "yellow";
  badge?: number;
}

const accentColors = {
  blue: "text-blue-400",
  red: "text-red-400",
  green: "text-emerald-400",
  yellow: "text-yellow-400",
};

export default function StatCard({ label, value, sub, accent = "blue", badge }: StatCardProps) {
  return (
    <div className="card relative">
      {badge !== undefined && badge > 0 && (
        <span className="absolute -right-1 -top-1 flex h-5 min-w-5 items-center justify-center rounded-full bg-red-500 px-1.5 text-[10px] font-bold text-white">
          {badge}
        </span>
      )}
      <p className="text-xs font-medium uppercase tracking-wider text-gray-500">{label}</p>
      <p className={clsx("mt-1 text-2xl font-bold tabular-nums", accentColors[accent])}>
        {value}
      </p>
      {sub && <p className="mt-0.5 text-xs text-gray-500">{sub}</p>}
    </div>
  );
}
