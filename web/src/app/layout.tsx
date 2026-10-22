import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Pointage EIGSI Casablanca",
  description: "Pointage et suivi des heures de présence du personnel EIGSI.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="fr">
      <body>{children}</body>
    </html>
  );
}
