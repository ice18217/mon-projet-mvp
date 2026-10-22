"use client";

import { useCallback, useEffect, useState } from "react";

import { type AlertItem, getDailyAlerts, resolveAlert } from "./actions";

const loadErrors = {
  unauthorized: "Votre session a expiré. Reconnectez-vous.",
  forbidden: "Les alertes sont réservées aux comptes RH/Scolarité.",
  unavailable: "Les alertes sont indisponibles. Vérifiez l’API et réessayez.",
  invalid: "La date demandée est invalide.",
} as const;

const typeLabels = {
  absence: "Absence",
  retard: "Retard",
} as const;

function todayInCasablanca(): string {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Africa/Casablanca",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date());
  const values = Object.fromEntries(
    parts.map((part) => [part.type, part.value]),
  );
  return `${values.year}-${values.month}-${values.day}`;
}

function formatTime(timestamp: string): string {
  return new Date(timestamp).toLocaleTimeString("fr-FR", {
    timeZone: "Africa/Casablanca",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function AlertManager() {
  const [date, setDate] = useState("");
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [threshold, setThreshold] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState<string | null>(null);
  const [resolving, setResolving] = useState<string | null>(null);

  const refresh = useCallback(async (day: string) => {
    setLoading(true);
    setMessage(null);
    setAlerts([]);
    setThreshold(null);
    const result = await getDailyAlerts(day);
    if (!result.ok) {
      setMessage(loadErrors[result.code]);
      setLoading(false);
      return;
    }
    setAlerts(result.alerts);
    setThreshold(result.thresholdMinutes);
    setLoading(false);
  }, []);

  useEffect(() => {
    setDate(todayInCasablanca());
  }, []);

  useEffect(() => {
    if (date) {
      void refresh(date);
    }
  }, [date, refresh]);

  async function markResolved(alertId: string) {
    setResolving(alertId);
    setMessage(null);
    const result = await resolveAlert(alertId);
    if (!result.ok) {
      setMessage(loadErrors[result.code]);
      setResolving(null);
      return;
    }
    await refresh(date);
    setResolving(null);
  }

  return (
    <section className="card card-wide alert-manager">
      <p className="eyebrow">EIGSI Casablanca</p>
      <h1>Alertes de présence</h1>
      <p>
        Les alertes sont évaluées lors de la consultation par RH/Scolarité. Un
        retard est déclenché après {threshold ?? 10} minutes de tolérance; une
        absence est évaluée après la fin du créneau sans entrée enregistrée.
      </p>

      <label className="date-label" htmlFor="alert-date">
        Journée
      </label>
      <input
        id="alert-date"
        onChange={(event) => setDate(event.target.value)}
        type="date"
        value={date}
      />

      {message ? (
        <p aria-live="assertive" className="error">
          {message}
        </p>
      ) : null}
      {loading ? <p aria-live="polite">Évaluation des alertes…</p> : null}
      {!loading && !message && alerts.length === 0 ? (
        <p>Aucune alerte pour cette journée.</p>
      ) : null}
      {alerts.length > 0 ? (
        <ul className="alert-list">
          {alerts.map((alert) => (
            <li
              className={`alert-item ${alert.statut === "traitee" ? "alert-resolved" : ""}`}
              key={alert.id}
            >
              <div>
                <h2>
                  {typeLabels[alert.type]} — {alert.prenom} {alert.nom}
                </h2>
                <p>
                  Créneau {formatTime(alert.debut)}–{formatTime(alert.fin)} ·{" "}
                  {alert.type_activite}
                </p>
                <p>
                  Détectée le{" "}
                  {new Date(alert.date_alerte).toLocaleString("fr-FR", {
                    timeZone: "Africa/Casablanca",
                    dateStyle: "short",
                    timeStyle: "short",
                  })}
                  {" · "}
                  {alert.statut === "envoyee" ? "À traiter" : "Traitée"}
                </p>
              </div>
              {alert.statut === "envoyee" ? (
                <button
                  disabled={resolving === alert.id}
                  onClick={() => void markResolved(alert.id)}
                  type="button"
                >
                  {resolving === alert.id ? "Mise à jour…" : "Marquer traitée"}
                </button>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
