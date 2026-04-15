"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";

const NAV = [
  { href: "/", label: "Command Center", icon: "⌘" },
  { href: "/universe", label: "Universe", icon: "◎" },
  { href: "/positions", label: "Positions", icon: "◆" },
  { href: "/predictions", label: "Predictions", icon: "◇" },
  { href: "/analytics", label: "Analytics", icon: "△" },
];

export default function Sidebar() {
  const pathname = usePathname();
  const isCompanyPage = pathname.startsWith("/company/");

  return (
    <nav className="hidden w-56 shrink-0 flex-col border-r border-nadir-border bg-nadir-surface lg:flex">
      <div className="flex h-14 items-center gap-2 border-b border-nadir-border px-5">
        <span className="text-lg font-bold tracking-widest text-nadir-accent">NADIR</span>
        <span className="text-[10px] text-gray-500">v1.0</span>
      </div>
      <div className="flex flex-1 flex-col gap-1 p-3">
        {NAV.map((item) => {
          const active = item.href === "/"
            ? pathname === "/"
            : pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={clsx(
                "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                active
                  ? "bg-nadir-accent/10 text-nadir-accent"
                  : "text-gray-400 hover:bg-gray-800 hover:text-gray-200"
              )}
            >
              <span className="text-base">{item.icon}</span>
              {item.label}
            </Link>
          );
        })}
      </div>
      <div className="border-t border-nadir-border p-4">
        <p className="text-[10px] uppercase tracking-widest text-gray-600">
          Narrative Adversarial Detection
        </p>
        <p className="text-[10px] uppercase tracking-widest text-gray-600">
          & Investment Recognition
        </p>
      </div>
    </nav>
  );
}
