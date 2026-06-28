import type { Metadata } from "next";
import Link from "next/link";
import { Activity, ShieldCheck } from "lucide-react";

import "./globals.css";

export const metadata: Metadata = {
  title: "IPO Lens AI",
  description: "Verifiable IPO intelligence platform"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header className="border-b border-zinc-200 bg-white">
          <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
            <Link href="/" className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded bg-ink text-white">
                <ShieldCheck className="h-5 w-5" aria-hidden="true" />
              </div>
              <div>
                <div className="font-semibold tracking-normal text-ink">IPO Lens AI</div>
                <div className="text-xs text-zinc-500">Verifiable IPO Intelligence</div>
              </div>
            </Link>
            <div className="hidden items-center gap-2 text-sm font-medium text-graphite sm:flex">
              <Activity className="h-4 w-4 text-mint" aria-hidden="true" />
              Evidence-first research
            </div>
          </div>
        </header>
        <main className="mx-auto max-w-7xl px-6 py-8">{children}</main>
      </body>
    </html>
  );
}

