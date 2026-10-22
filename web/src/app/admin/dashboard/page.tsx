import type { Metadata } from "next";

import { DashboardManager } from "./dashboard-manager";

export const metadata: Metadata = {
  title: "Tableau de bord de présence — EIGSI",
};

export default function DashboardPage() {
  return (
    <main className="page">
      <DashboardManager />
    </main>
  );
}
