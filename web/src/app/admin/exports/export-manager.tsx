"use client";

import { useEffect, useState } from "react";

import { downloadWeeklyPayrollExport } from "./actions";

const errorMessages = {
  unauthorized: "Votre session a expiré. Reconnectez-vous.",
  forbidden: "L’export est réservé aux comptes RH/Finance.",
  invalid: "Choisissez un lundi correspondant à une semaine terminée.",
  unavailable: "L’export est indisponible. Vérifiez l’API et réessayez.",
} as const;

function latestCompletedMonday(): string {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Africa/Casablanca",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date());
  const values = Object.fromEntries(
    parts.map((part) => [part.type, part.value]),
  );
  const today = new Date(
    `${values.year}-${values.month}-${values.day}T00:00:00Z`,
  );
  const daysSinceMonday = (today.getUTCDay() + 6) % 7;
  today.setUTCDate(today.getUTCDate() - daysSinceMonday - 7);
  return today.toISOString().slice(0, 10);
}

function endOfWeek(weekStart: string): string {
  const end = new Date(`${weekStart}T00:00:00Z`);
  end.setUTCDate(end.getUTCDate() + 6);
  return end.toISOString().slice(0, 10);
}

export function ExportManager() {
  const [weekStart, setWeekStart] = useState("");
  const [maximumWeek, setMaximumWeek] = useState("");
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    const latestMonday = latestCompletedMonday();
    setWeekStart(latestMonday);
    setMaximumWeek(latestMonday);
  }, []);

  async function download(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setDownloading(true);
    setError(null);
    setMessage(null);
    const result = await downloadWeeklyPayrollExport(weekStart);
    setDownloading(false);
    if (!result.ok) {
      setError(errorMessages[result.code]);
      return;
    }

    const blob = new Blob([result.csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `heures-eigsi-${weekStart}_${endOfWeek(weekStart)}.csv`;
    document.body.append(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    setMessage("Le CSV hebdomadaire a été téléchargé.");
  }

  return (
    <section
      aria-labelledby="export-title"
      className="card card-wide export-manager"
    >
      <p className="eyebrow">EIGSI Casablanca</p>
      <h1 id="export-title">Export hebdomadaire des heures</h1>
      <p>
        Téléchargement réservé à RH/Finance. Seules les journées complètes et
        cohérentes sont comptabilisées; une journée incomplète ou anomale est
        exclue du total et signalée pour revue. Le CSV ne constitue pas une
        validation de paie et aucun historique d’export n’est conservé.
      </p>

      <form className="export-form" onSubmit={download}>
        <label htmlFor="export-week">
          Lundi de la semaine à exporter
          <input
            id="export-week"
            max={maximumWeek || undefined}
            onChange={(event) => setWeekStart(event.target.value)}
            required
            type="date"
            value={weekStart}
          />
        </label>
        <p>
          Période locale : {weekStart || "—"} au{" "}
          {weekStart ? endOfWeek(weekStart) : "—"} (Africa/Casablanca)
        </p>
        <button disabled={downloading || !weekStart} type="submit">
          {downloading ? "Préparation du CSV…" : "Télécharger le CSV"}
        </button>
      </form>

      {error ? (
        <p aria-live="assertive" className="error">
          {error}
        </p>
      ) : null}
      {message ? <p aria-live="polite">{message}</p> : null}
      <a className="text-link" href="/">
        Retour à l’accueil
      </a>
    </section>
  );
}
