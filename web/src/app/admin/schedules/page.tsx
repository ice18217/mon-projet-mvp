import type { Metadata } from "next";

import { ScheduleManager } from "./schedule-manager";

export const metadata: Metadata = {
  title: "Gestion des horaires — EIGSI",
};

export default function SchedulesPage() {
  return (
    <main className="page">
      <ScheduleManager />
    </main>
  );
}
