import type { Metadata } from "next";

import { DailyAttendance } from "./daily-attendance";

export const metadata: Metadata = {
  title: "Mes heures de présence — EIGSI",
};

export default function MyAttendancePage() {
  return (
    <main className="page">
      <DailyAttendance />
    </main>
  );
}
