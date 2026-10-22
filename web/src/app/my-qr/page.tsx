import type { Metadata } from "next";

import { QRManager } from "./qr-manager";

export const metadata: Metadata = {
  title: "Mon QR de pointage — EIGSI",
};

export default function MyQrPage() {
  return (
    <main className="page">
      <QRManager />
    </main>
  );
}
