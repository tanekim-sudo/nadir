import clsx from "clsx";

const SIGNAL_LABELS = ["SI", "AS", "IB", "GRR", "ML"];

export default function ConditionDots({ met }: { met: number }) {
  return (
    <div className="flex gap-1">
      {SIGNAL_LABELS.map((label, i) => (
        <span
          key={label}
          className={clsx(
            "flex h-5 w-5 items-center justify-center rounded text-[9px] font-bold",
            i < met
              ? "bg-red-500/80 text-white"
              : "bg-gray-800 text-gray-600"
          )}
          title={label}
        >
          {label}
        </span>
      ))}
    </div>
  );
}
