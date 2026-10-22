import type { Metadata } from "next";

import { AlertManager } from "./alert-manager";

export const metadata: Metadata = {
  title: "Alertes de présence — EIGSI",
};

export default function AlertsPage() {
  return (
    <main className="page">
      <AlertManager />
    </main>
  );
}
