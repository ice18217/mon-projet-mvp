"use client";

import { useEffect, useState } from "react";

import { type DailyAttendanceResult, getDailyAttendance } from "./actions";

const statusMessages = {
  complete: "Tous les intervalles de la journée sont complets.",
  incomplete: "Une entrée n’a pas encore de sortie. Elle n’est pas comptée.",
  anomaly:
    "Des événements sont incohérents ou ont le même horodatage; ils sont exclus.",
  incomplete_anomaly:
    "La journée contient des intervalles incomplets et des événements incohérents.",
} as const;

const errorMessages = {
  unauthorized: "Votre session a expiré. Reconnectez-vous.",
  forbidden: "Cette page est réservée aux comptes Personnel approuvés.",
  unavailable:
    "Le résumé des heures est indisponible. Vérifiez la configuration et réessayez.",
  invalid: "La date demandée est invalide.",
} as const;

function todayInCasablanca(): string {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Africa/Casablanca",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date());
  const value = Object.fromEntries(
    parts.map((part) => [part.type, part.value]),
  );
  return `${value.year}-${value.month}-${value.day}`;
}

function formatDuration(totalSeconds: number): string {
  const totalMinutes = Math.floor(totalSeconds / 60);
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  return `${hours} h ${minutes.toString().padStart(2, "0")} min`;
}

function formatTime(timestamp: string): string {
  return new Date(timestamp).toLocaleTimeString("fr-FR", {
    timeZone: "Africa/Casablanca",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function DailyAttendance() {
  const [selectedDate, setSelectedDate] = useState("");
  const [maximumDate, setMaximumDate] = useState("");
  const [summary, setSummary] = useState<DailyAttendanceResult | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const today = todayInCasablanca();
    setSelectedDate(today);
    setMaximumDate(today);
  }, []);

  useEffect(() => {
    if (!selectedDate) {
      return;
    }

    let cancelled = false;
    setLoading(true);
    setSummary(null);

    void getDailyAttendance(selectedDate).then((result) => {
      if (cancelled) {
        return;
      }
      setSummary(result);
      setLoading(false);
    });

    return () => {
      cancelled = true;
    };
  }, [selectedDate]);

  return (
    <section className="card daily-card" aria-labelledby="daily-title">
      <p className="eyebrow">EIGSI Casablanca</p>
      <h1 id="daily-title">Mes heures de présence</h1>
      <p>
        Consultez les intervalles Entrée/Sortie complets enregistrés pour une
        journée. Les heures sont affichées dans le fuseau de Casablanca.
      </p>

      <label className="date-label" htmlFor="attendance-date">
        Journée
      </label>
      <input
        id="attendance-date"
        max={maximumDate || undefined}
        onChange={(event) => setSelectedDate(event.target.value)}
        type="date"
        value={selectedDate}
      />

      {loading ? <p aria-live="polite">Calcul des heures…</p> : null}
      {summary && !summary.ok ? (
        <p aria-live="assertive" className="error">
          {errorMessages[summary.code]}
        </p>
      ) : null}

      {summary?.ok ? (
        <div aria-live="polite" className="daily-summary">
          <div className="total-hours">
            <span>Total constaté</span>
            <strong>{formatDuration(summary.totalSeconds)}</strong>
          </div>
          {summary.eventCount === 0 ? (
            <p>Aucun pointage enregistré pour cette journée.</p>
          ) : (
            <p className={summary.status === "complete" ? "notice" : "error"}>
              {statusMessages[summary.status]}
            </p>
          )}
          {summary.intervals.length > 0 ? (
            <div className="table-scroll">
              <table>
                <caption>
                  Intervalles de présence retenus dans le calcul
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Entrée</th>
                    <th scope="col">Sortie</th>
                    <th scope="col">Durée</th>
                  </tr>
                </thead>
                <tbody>
                  {summary.intervals.map((interval) => (
                    <tr key={`${interval.entree}-${interval.sortie}`}>
                      <td>{formatTime(interval.entree)}</td>
                      <td>{formatTime(interval.sortie)}</td>
                      <td>{formatDuration(interval.dureeSecondes)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
          <p className="hint">
            Ce total est calculé à partir des pointages enregistrés. Il ne
            constitue pas une validation pour la paie.
          </p>
        </div>
      ) : null}
    </section>
  );
}
