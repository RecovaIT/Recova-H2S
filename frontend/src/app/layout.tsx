import type { Metadata } from "next";
import localFont from "next/font/local";
import { AuthProvider } from "@/hooks/useAuth";
import { ToastProvider } from "@/components/ui/toast";
import "./globals.css";

const montserrat = localFont({
  src: "../fonts/montserrat-normal.woff2",
  weight: "300 800",
  variable: "--font-montserrat",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Recova — Anticipatory Health Intelligence Platform",
  description:
    "Clinical-grade shared six-agent anticipatory health platform supporting Recova Core, Loop, Neuro, and WorkSafe.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      className={montserrat.variable}
    >
      <body className="min-h-full bg-slate-50 text-slate-900">
        <ToastProvider>
          <AuthProvider>{children}</AuthProvider>
        </ToastProvider>
      </body>
    </html>
  );
}
