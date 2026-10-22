import type { Metadata } from "next";

import { CorrectionsManager } from "./corrections-manager";

export const metadata: Metadata = {
  title: "Corrections des pointages — EIGSI",
};

export default function CorrectionsPage() {
  return (
    <main className="page">
      <CorrectionsManager />
    </main>
  );
}
