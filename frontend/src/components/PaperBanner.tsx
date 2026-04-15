"use client";
import { useEffect, useState } from "react";
import { getHealth } from "@/lib/api";

export default function PaperBanner() {
  const [mode, setMode] = useState<string | null>(null);

  useEffect(() => {
    getHealth()
      .then((h) => setMode(h.mode))
      .catch(() => setMode("paper"));
  }, []);

  if (mode === "LIVE") return null;

  return (
    <div className="fixed left-0 right-0 top-0 z-50 flex h-8 items-center justify-center bg-amber-600 text-xs font-bold uppercase tracking-widest text-black">
      Paper Trading Mode — No Real Money At Risk
    </div>
  );
}
