import type { Metadata } from "next";

import { ExportManager } from "./export-manager";

export const metadata: Metadata = {
  title: "Export hebdomadaire — EIGSI",
};

export default function PayrollExportPage() {
  return (
    <main className="page">
      <ExportManager />
    </main>
  );
}
