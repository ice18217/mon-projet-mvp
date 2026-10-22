"use server";

import { createClient } from "@/lib/supabase/server";

export type DashboardStatus =
  | "present"
  | "retard"
  | "absent"
  | "en_attente"
  | "sans_horaire";

export type CalculationStatus =
  | "complete"
  | "incomplete"
  | "anomaly"
  | "incomplete_anomaly";

export type DashboardPerson = {
  id_personnel: string;
  nom: string;
  prenom: string;
  statut_presence: DashboardStatus;
  debut_horaire: string | null;
  fin_horaire: string | null;
  type_activite: string | null;
  total_secondes: number;
  etat_calcul: CalculationStatus;
  nombre_pointages: number;
};

export type AttendanceDashboardResult =
  | {
      ok: true;
      date: string;
      effectif: number;
      compteurs: Record<DashboardStatus, number>;
      personnel: DashboardPerson[];
    }
  | {
      ok: false;
      code: "unauthorized" | "forbidden" | "unavailable" | "invalid";
    };

const dashboardStatuses: DashboardStatus[] = [
  "present",
  "retard",
  "absent",
  "en_attente",
  "sans_horaire",
];

const calculationStatuses: CalculationStatus[] = [
  "complete",
  "incomplete",
  "anomaly",
  "incomplete_anomaly",
];

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isUuid(value: unknown): value is string {
  return (
    typeof value === "string" &&
    /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(
      value,
    )
  );
}

function isValidDate(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    return false;
  }
  const parsed = new Date(`${value}T00:00:00Z`);
  return (
    Number.isFinite(parsed.getTime()) &&
    parsed.toISOString().slice(0, 10) === value
  );
}

async function getAccessToken(): Promise<string | null> {
  if (
    !process.env.NEXT_PUBLIC_SUPABASE_URL ||
    !process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
  ) {
    return null;
  }
  const supabase = await createClient();
  const {
    data: { user },
    error: userError,
  } = await supabase.auth.getUser();
  if (userError || !user) {
    return null;
  }
  const {
    data: { session },
  } = await supabase.auth.getSession();
  return session?.access_token ?? null;
}

function parsePerson(value: unknown): DashboardPerson | null {
  if (
    !isObject(value) ||
    !isUuid(value.id_personnel) ||
    typeof value.nom !== "string" ||
    typeof value.prenom !== "string" ||
    !dashboardStatuses.includes(value.statut_presence as DashboardStatus) ||
    !(
      value.debut_horaire === null ||
      (typeof value.debut_horaire === "string" &&
        Number.isFinite(Date.parse(value.debut_horaire)))
    ) ||
    !(
      value.fin_horaire === null ||
      (typeof value.fin_horaire === "string" &&
        Number.isFinite(Date.parse(value.fin_horaire)))
    ) ||
    !(
      value.type_activite === null || typeof value.type_activite === "string"
    ) ||
    !Number.isSafeInteger(value.total_secondes) ||
    (value.total_secondes as number) < 0 ||
    !calculationStatuses.includes(value.etat_calcul as CalculationStatus) ||
    !Number.isSafeInteger(value.nombre_pointages) ||
    (value.nombre_pointages as number) < 0
  ) {
    return null;
  }
  return {
    id_personnel: value.id_personnel,
    nom: value.nom,
    prenom: value.prenom,
    statut_presence: value.statut_presence as DashboardStatus,
    debut_horaire: value.debut_horaire,
    fin_horaire: value.fin_horaire,
    type_activite: value.type_activite,
    total_secondes: value.total_secondes as number,
    etat_calcul: value.etat_calcul as CalculationStatus,
    nombre_pointages: value.nombre_pointages as number,
  };
}

export async function getAttendanceDashboard(
  date: string,
): Promise<AttendanceDashboardResult> {
  if (!isValidDate(date)) {
    return { ok: false, code: "invalid" };
  }
  const token = await getAccessToken();
  if (!token) {
    return { ok: false, code: "unauthorized" };
  }
  const apiUrl = process.env.NEXT_PUBLIC_API_URL;
  if (!apiUrl) {
    return { ok: false, code: "unavailable" };
  }

  let response: Response;
  try {
    response = await fetch(
      `${apiUrl.replace(/\/$/, "")}/attendance/dashboard?date=${encodeURIComponent(date)}`,
      {
        headers: { Authorization: `Bearer ${token}` },
        cache: "no-store",
      },
    );
  } catch (error) {
    console.error("Unable to reach the attendance-dashboard API.", error);
    return { ok: false, code: "unavailable" };
  }
  if (response.status === 401) {
    return { ok: false, code: "unauthorized" };
  }
  if (response.status === 403) {
    return { ok: false, code: "forbidden" };
  }
  if (response.status === 422) {
    return { ok: false, code: "invalid" };
  }
  if (!response.ok) {
    console.error("Dashboard request failed with API status", response.status);
    return { ok: false, code: "unavailable" };
  }

  let body: unknown;
  try {
    body = await response.json();
  } catch (error) {
    console.error("The dashboard API returned invalid JSON.", error);
    return { ok: false, code: "unavailable" };
  }
  if (
    !isObject(body) ||
    body.date !== date ||
    body.fuseau_horaire !== "Africa/Casablanca" ||
    !Number.isSafeInteger(body.effectif) ||
    !isObject(body.compteurs) ||
    !Array.isArray(body.personnel)
  ) {
    console.error("The dashboard API returned an invalid response.");
    return { ok: false, code: "unavailable" };
  }

  const people: DashboardPerson[] = [];
  for (const item of body.personnel) {
    const person = parsePerson(item);
    if (!person) {
      console.error("The dashboard API returned an invalid personnel record.");
      return { ok: false, code: "unavailable" };
    }
    people.push(person);
  }

  const counts = {} as Record<DashboardStatus, number>;
  const actualCounts = Object.fromEntries(
    dashboardStatuses.map((status) => [
      status,
      people.filter((person) => person.statut_presence === status).length,
    ]),
  ) as Record<DashboardStatus, number>;
  for (const status of dashboardStatuses) {
    const count = body.compteurs[status];
    if (!Number.isSafeInteger(count) || (count as number) < 0) {
      console.error("The dashboard API returned invalid status counts.");
      return { ok: false, code: "unavailable" };
    }
    counts[status] = count as number;
  }
  if (
    body.effectif !== people.length ||
    dashboardStatuses.reduce((sum, status) => sum + counts[status], 0) !==
      people.length ||
    dashboardStatuses.some((status) => counts[status] !== actualCounts[status])
  ) {
    console.error("The dashboard API returned inconsistent counts.");
    return { ok: false, code: "unavailable" };
  }

  return {
    ok: true,
    date,
    effectif: body.effectif as number,
    compteurs: counts,
    personnel: people,
  };
}
