import type { Metadata } from "next";

import { AttendanceScanner } from "./scanner";

export const metadata: Metadata = {
  title: "Pointage par QR — EIGSI",
};

export default function AttendancePage() {
  return (
    <main className="page">
      <AttendanceScanner />
    </main>
  );
}
