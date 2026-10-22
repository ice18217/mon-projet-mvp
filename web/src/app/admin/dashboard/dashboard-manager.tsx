"use client";

import { useEffect, useState } from "react";

import {
  type AttendanceDashboardResult,
  type DashboardPerson,
  type DashboardStatus,
  getAttendanceDashboard,
} from "./actions";

const errorMessages = {
  unauthorized: "Votre session a expiré. Reconnectez-vous.",
  forbidden: "Le tableau de bord est réservé aux comptes RH/Scolarité.",
  unavailable:
    "Le tableau de bord est indisponible. Vérifiez l’API et réessayez.",
  invalid: "La date sélectionnée est invalide ou future.",
} as const;

const statusLabels: Record<DashboardStatus, string> = {
  present: "Présent",
  retard: "En retard",
  absent: "Absent",
  en_attente: "En attente",
  sans_horaire: "Aucun horaire",
};

const calculationLabels = {
  complete: "Calcul complet",
  incomplete: "Entrée sans sortie",
  anomaly: "Anomalie de pointage",
  incomplete_anomaly: "Pointage incomplet et anomalie",
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

function formatDuration(totalSeconds: number): string {
  const minutes = Math.floor(totalSeconds / 60);
  return `${Math.floor(minutes / 60)} h ${String(minutes % 60).padStart(2, "0")} min`;
}

function formatTime(timestamp: string): string {
  return new Date(timestamp).toLocaleTimeString("fr-FR", {
    timeZone: "Africa/Casablanca",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatSchedule(person: DashboardPerson): string {
  if (!person.debut_horaire || !person.fin_horaire) {
    return "—";
  }
  return `${formatTime(person.debut_horaire)}–${formatTime(person.fin_horaire)}`;
}

export function DashboardManager() {
  const [date, setDate] = useState("");
  const [maximumDate, setMaximumDate] = useState("");
  const [result, setResult] = useState<AttendanceDashboardResult | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const today = todayInCasablanca();
    setDate(today);
    setMaximumDate(today);
  }, []);

  useEffect(() => {
    if (!date) {
      return;
    }
    let cancelled = false;
    setLoading(true);
    setResult(null);
    void getAttendanceDashboard(date).then((dashboard) => {
      if (!cancelled) {
        setResult(dashboard);
        setLoading(false);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [date]);

  return (
    <section
      aria-labelledby="dashboard-title"
      className="card card-wide dashboard-card"
    >
      <p className="eyebrow">EIGSI Casablanca</p>
      <h1 id="dashboard-title">Tableau de bord de présence</h1>
      <p className="dashboard-description">
        Situation journalière du personnel actif, selon les horaires et les
        pointages enregistrés. Les heures calculées ne sont pas une validation
        de paie.
      </p>

      <label className="date-label" htmlFor="dashboard-date">
        Journée
      </label>
      <input
        id="dashboard-date"
        max={maximumDate || undefined}
        onChange={(event) => setDate(event.target.value)}
        type="date"
        value={date}
      />

      {loading ? (
        <p aria-live="polite">Chargement du tableau de bord…</p>
      ) : null}
      {result && !result.ok ? (
        <p aria-live="assertive" className="error">
          {errorMessages[result.code]}
        </p>
      ) : null}
      {result?.ok ? (
        <>
          <dl aria-label="Effectifs par statut" className="dashboard-counts">
            <div>
              <dt>Présents</dt>
              <dd>{result.compteurs.present}</dd>
            </div>
            <div>
              <dt>En retard</dt>
              <dd>{result.compteurs.retard}</dd>
            </div>
            <div>
              <dt>Absents</dt>
              <dd>{result.compteurs.absent}</dd>
            </div>
            <div>
              <dt>En attente</dt>
              <dd>{result.compteurs.en_attente}</dd>
            </div>
            <div>
              <dt>Sans horaire</dt>
              <dd>{result.compteurs.sans_horaire}</dd>
            </div>
          </dl>

          {result.personnel.length === 0 ? (
            <p>Aucun membre du personnel actif pour cette journée.</p>
          ) : (
            <div className="table-scroll">
              <table className="dashboard-table">
                <caption>
                  Présence du personnel — {result.effectif} personne
                  {result.effectif > 1 ? "s" : ""}
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Personnel</th>
                    <th scope="col">Statut</th>
                    <th scope="col">Horaire</th>
                    <th scope="col">Activité</th>
                    <th scope="col">Temps calculé</th>
                    <th scope="col">Pointages / état</th>
                  </tr>
                </thead>
                <tbody>
                  {result.personnel.map((person) => (
                    <tr key={person.id_personnel}>
                      <th scope="row">
                        {person.prenom} {person.nom}
                      </th>
                      <td>
                        <span
                          className={`dashboard-status dashboard-status-${person.statut_presence}`}
                        >
                          {statusLabels[person.statut_presence]}
                        </span>
                      </td>
                      <td>{formatSchedule(person)}</td>
                      <td>{person.type_activite ?? "—"}</td>
                      <td>{formatDuration(person.total_secondes)}</td>
                      <td>
                        {person.nombre_pointages} ·{" "}
                        {calculationLabels[person.etat_calcul]}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      ) : null}
    </section>
  );
}
