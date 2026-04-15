import type { Metadata } from "next";
import "./globals.css";
import Sidebar from "@/components/Sidebar";
import PaperBanner from "@/components/PaperBanner";

export const metadata: Metadata = {
  title: "NADIR — Investment Intelligence",
  description: "Narrative Adversarial Detection and Investment Recognition",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="bg-nadir-bg text-gray-100 antialiased">
        <PaperBanner />
        <div className="flex h-screen pt-8">
          <Sidebar />
          <main className="flex-1 overflow-y-auto p-6 lg:p-8">{children}</main>
        </div>
      </body>
    </html>
  );
}
