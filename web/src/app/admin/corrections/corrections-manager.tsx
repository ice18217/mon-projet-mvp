"use client";

import { useEffect, useState } from "react";

import {
  type AttendanceCorrectionsResult,
  type AttendancePointageCorrection,
  getAttendanceCorrections,
  saveAttendanceCorrection,
} from "./actions";

const errorMessages = {
  unauthorized: "Votre session a expiré. Reconnectez-vous.",
  forbidden: "Les corrections sont réservées aux comptes RH/Scolarité.",
  unavailable:
    "Les corrections sont indisponibles. Vérifiez l’API et réessayez.",
  invalid: "La correction est invalide. Vérifiez la date, l’heure et le motif.",
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

function formatTimestamp(timestamp: string): string {
  return new Date(timestamp).toLocaleString("fr-FR", {
    timeZone: "Africa/Casablanca",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function localTime(timestamp: string): string {
  return new Date(timestamp).toLocaleTimeString("fr-FR", {
    timeZone: "Africa/Casablanca",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function CorrectionForm({
  date,
  pointage,
  onSaved,
}: {
  date: string;
  pointage: AttendancePointageCorrection;
  onSaved: () => void;
}) {
  const [heure, setHeure] = useState(() =>
    localTime(pointage.date_heure_effective),
  );
  const [motif, setMotif] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    const result = await saveAttendanceCorrection(
      pointage.id_pointage,
      date,
      heure,
      motif,
    );
    setSaving(false);
    if (!result.ok) {
      setError(errorMessages[result.code]);
      return;
    }
    setMotif("");
    onSaved();
  }

  return (
    <form className="correction-form" onSubmit={submit}>
      <label>
        Heure effective
        <input
          onChange={(event) => setHeure(event.target.value)}
          required
          type="time"
          value={heure}
        />
      </label>
      <label>
        Motif obligatoire
        <input
          maxLength={500}
          minLength={5}
          onChange={(event) => setMotif(event.target.value)}
          required
          type="text"
          value={motif}
        />
      </label>
      <button disabled={saving} type="submit">
        {saving ? "Enregistrement…" : "Enregistrer la correction"}
      </button>
      {error ? (
        <p aria-live="assertive" className="error">
          {error}
        </p>
      ) : null}
    </form>
  );
}

export function CorrectionsManager() {
  const [date, setDate] = useState("");
  const [maximumDate, setMaximumDate] = useState("");
  const [result, setResult] = useState<AttendanceCorrectionsResult | null>(
    null,
  );
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const today = todayInCasablanca();
    setDate(today);
    setMaximumDate(today);
  }, []);

  useEffect(() => {
    if (!date) return;
    let cancelled = false;
    setLoading(true);
    setResult(null);
    void getAttendanceCorrections(date)
      .then((data) => {
        if (!cancelled) setResult(data);
      })
      .catch((error: unknown) => {
        console.error("Unable to load attendance corrections.", error);
        if (!cancelled) setResult({ ok: false, code: "unavailable" });
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [date]);

  function reloadCorrections() {
    if (!date) return;
    setLoading(true);
    void getAttendanceCorrections(date)
      .then(setResult)
      .catch((error: unknown) => {
        console.error("Unable to reload attendance corrections.", error);
        setResult({ ok: false, code: "unavailable" });
      })
      .finally(() => setLoading(false));
  }

  return (
    <section
      aria-labelledby="corrections-title"
      className="card card-wide corrections-manager"
    >
      <p className="eyebrow">EIGSI Casablanca</p>
      <h1 id="corrections-title">Corrections des pointages</h1>
      <p>
        Les corrections sont réservées à RH/Scolarité. L’heure originale est
        conservée et chaque modification est ajoutée à l’historique. Une heure
        corrigée doit rester dans la même journée locale Africa/Casablanca.
      </p>
      <label className="date-label" htmlFor="corrections-date">
        Journée à consulter
      </label>
      <input
        id="corrections-date"
        max={maximumDate || undefined}
        onChange={(event) => setDate(event.target.value)}
        type="date"
        value={date}
      />

      {loading ? <p aria-live="polite">Chargement des pointages…</p> : null}
      {result && !result.ok ? (
        <p aria-live="assertive" className="error">
          {errorMessages[result.code]}
        </p>
      ) : null}
      {result?.ok && result.pointages.length === 0 ? (
        <p>Aucun pointage enregistré pour cette journée.</p>
      ) : null}
      {result?.ok && result.pointages.length > 0 ? (
        <div className="correction-list">
          {result.pointages.map((pointage) => (
            <PointageCorrection
              key={`${pointage.id_pointage}-${pointage.date_heure_effective}`}
              date={date}
              onSaved={reloadCorrections}
              pointage={pointage}
            />
          ))}
        </div>
      ) : null}
      <a className="text-link" href="/">
        Retour à l’accueil
      </a>
    </section>
  );
}

function PointageCorrection({
  date,
  pointage,
  onSaved,
}: {
  date: string;
  pointage: AttendancePointageCorrection;
  onSaved: () => void;
}) {
  return (
    <article className="correction-item">
      <div className="correction-heading">
        <div>
          <h2>
            {pointage.prenom} {pointage.nom}
          </h2>
          <p>
            {pointage.type_pointage === "entree" ? "Entrée" : "Sortie"} ·{" "}
            pointage original {formatTimestamp(pointage.date_heure_originale)}
          </p>
        </div>
        <p>
          Heure effective :{" "}
          <strong>{formatTimestamp(pointage.date_heure_effective)}</strong>
        </p>
      </div>
      {pointage.historique.length > 0 ? (
        <details>
          <summary>
            Historique des corrections ({pointage.historique.length})
          </summary>
          <ol className="correction-history">
            {pointage.historique.map((entry) => (
              <li key={`${pointage.id_pointage}-${entry.revision}`}>
                <strong>Correction {entry.revision}</strong> —{" "}
                {formatTimestamp(entry.ancienne_valeur)} →{" "}
                {formatTimestamp(entry.nouvelle_valeur)} ; {entry.motif}
                <span>
                  Enregistrée le {formatTimestamp(entry.date_correction)}
                </span>
              </li>
            ))}
          </ol>
        </details>
      ) : (
        <p>Aucune correction antérieure.</p>
      )}
      <CorrectionForm date={date} onSaved={onSaved} pointage={pointage} />
    </article>
  );
}
