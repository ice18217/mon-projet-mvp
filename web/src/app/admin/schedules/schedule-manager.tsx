"use client";

import type { FormEvent } from "react";
import { useCallback, useEffect, useState } from "react";

import {
  getSchedules,
  type ScheduleItem,
  type SchedulePerson,
  saveSchedule,
} from "./actions";

type LoadState = "loading" | "ready" | "error";

const loadErrors = {
  unauthorized: "Votre session a expiré. Reconnectez-vous.",
  forbidden: "La gestion des horaires est réservée aux comptes RH/Scolarité.",
  unavailable: "Les horaires sont indisponibles. Vérifiez l’API et réessayez.",
  invalid: "La date sélectionnée est invalide.",
} as const;

const saveErrors = {
  unauthorized: "Votre session a expiré. Reconnectez-vous.",
  forbidden: "Un rôle RH/Scolarité actif est nécessaire pour enregistrer.",
  unavailable: "L’enregistrement a échoué. Vérifiez l’API et réessayez.",
  invalid: "Vérifiez la personne, la date, les heures et l’activité.",
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

export function ScheduleManager() {
  const [date, setDate] = useState("");
  const [personnel, setPersonnel] = useState<SchedulePerson[]>([]);
  const [schedules, setSchedules] = useState<ScheduleItem[]>([]);
  const [state, setState] = useState<LoadState>("loading");
  const [selectedPersonnel, setSelectedPersonnel] = useState("");
  const [startTime, setStartTime] = useState("08:00");
  const [endTime, setEndTime] = useState("17:00");
  const [activity, setActivity] = useState("Travail");
  const [message, setMessage] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const refreshSchedules = useCallback(
    async (day: string, clearMessage = true) => {
      setState("loading");
      if (clearMessage) {
        setMessage(null);
      }
      const result = await getSchedules(day);
      if (!result.ok) {
        setState("error");
        setPersonnel([]);
        setSchedules([]);
        setMessage(loadErrors[result.code]);
        return;
      }
      setPersonnel(result.personnel);
      setSchedules(result.horaires);
      setState("ready");
    },
    [],
  );

  useEffect(() => {
    setDate(todayInCasablanca());
  }, []);

  useEffect(() => {
    if (date) {
      void refreshSchedules(date);
    }
  }, [date, refreshSchedules]);

  function editSchedule(schedule: ScheduleItem) {
    setSelectedPersonnel(schedule.id_personnel);
    setStartTime(schedule.heure_debut);
    setEndTime(schedule.heure_fin);
    setActivity(schedule.type_activite);
    setMessage(null);
  }

  async function submitSchedule(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!date || !selectedPersonnel) {
      setMessage("Sélectionnez un membre du personnel et une date.");
      return;
    }

    setSaving(true);
    setMessage(null);
    const result = await saveSchedule({
      id_personnel: selectedPersonnel,
      date,
      heure_debut: startTime,
      heure_fin: endTime,
      type_activite: activity,
    });
    if (!result.ok) {
      setMessage(saveErrors[result.code]);
      setSaving(false);
      return;
    }
    setMessage("L’horaire a été enregistré.");
    await refreshSchedules(date, false);
    setSaving(false);
  }

  return (
    <section className="card card-wide schedule-manager">
      <p className="eyebrow">EIGSI Casablanca</p>
      <h1>Gestion des horaires</h1>
      <p>
        Un seul créneau par personne et par journée. Les horaires sont saisis
        dans le fuseau de Casablanca; une fin après minuit n’est pas acceptée.
      </p>

      <label className="date-label" htmlFor="schedule-date">
        Journée
      </label>
      <input
        id="schedule-date"
        onChange={(event) => {
          const selectedDate = event.target.value;
          setDate(selectedDate);
          setMessage(null);
          if (!selectedDate) {
            setSchedules([]);
            setState("ready");
          }
        }}
        type="date"
        value={date}
      />

      <form className="schedule-form" onSubmit={submitSchedule}>
        <label>
          Personnel actif
          <select
            onChange={(event) => setSelectedPersonnel(event.target.value)}
            required
            value={selectedPersonnel}
          >
            <option value="">Sélectionner une personne</option>
            {personnel.map((person) => (
              <option key={person.id} value={person.id}>
                {person.prenom} {person.nom} — {person.email}
              </option>
            ))}
          </select>
        </label>
        <label>
          Début
          <input
            onChange={(event) => setStartTime(event.target.value)}
            required
            type="time"
            value={startTime}
          />
        </label>
        <label>
          Fin
          <input
            onChange={(event) => setEndTime(event.target.value)}
            required
            type="time"
            value={endTime}
          />
        </label>
        <label>
          Activité
          <input
            maxLength={120}
            onChange={(event) => setActivity(event.target.value)}
            required
            type="text"
            value={activity}
          />
        </label>
        <button
          disabled={saving || !date || personnel.length === 0}
          type="submit"
        >
          {saving ? "Enregistrement…" : "Enregistrer l’horaire"}
        </button>
      </form>

      {message ? (
        <p
          aria-live="polite"
          className={
            message === "L’horaire a été enregistré." ? "notice" : "error"
          }
        >
          {message}
        </p>
      ) : null}
      {state === "loading" ? (
        <p aria-live="polite">Chargement des horaires…</p>
      ) : null}
      {state === "ready" && schedules.length === 0 ? (
        <p>Aucun horaire enregistré pour cette journée.</p>
      ) : null}
      {schedules.length > 0 ? (
        <div className="table-scroll">
          <table>
            <caption>Créneaux de la journée</caption>
            <thead>
              <tr>
                <th scope="col">Personnel</th>
                <th scope="col">Début</th>
                <th scope="col">Fin</th>
                <th scope="col">Activité</th>
                <th scope="col">Action</th>
              </tr>
            </thead>
            <tbody>
              {schedules.map((schedule) => (
                <tr key={schedule.id}>
                  <td>
                    {schedule.prenom} {schedule.nom}
                  </td>
                  <td>{schedule.heure_debut}</td>
                  <td>{schedule.heure_fin}</td>
                  <td>{schedule.type_activite}</td>
                  <td>
                    <button
                      className="secondary-button"
                      onClick={() => editSchedule(schedule)}
                      type="button"
                    >
                      Modifier
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </section>
  );
}
