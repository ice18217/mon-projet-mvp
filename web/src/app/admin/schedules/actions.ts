"use server";

import { createClient } from "@/lib/supabase/server";

export type SchedulePerson = {
  id: string;
  nom: string;
  prenom: string;
  email: string;
};

export type ScheduleItem = {
  id: string;
  id_personnel: string;
  date: string;
  heure_debut: string;
  heure_fin: string;
  type_activite: string;
  nom: string;
  prenom: string;
};

export type ScheduleOverviewResult =
  | { ok: true; personnel: SchedulePerson[]; horaires: ScheduleItem[] }
  | {
      ok: false;
      code: "unauthorized" | "forbidden" | "unavailable" | "invalid";
    };

export type SaveScheduleResult =
  | { ok: true }
  | {
      ok: false;
      code: "unauthorized" | "forbidden" | "unavailable" | "invalid";
    };

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
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

function isUuid(value: unknown): value is string {
  return (
    typeof value === "string" &&
    /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(
      value,
    )
  );
}

export async function getSchedules(
  date: string,
): Promise<ScheduleOverviewResult> {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) {
    return { ok: false, code: "invalid" };
  }
  const accessToken = await getAccessToken();
  if (!accessToken) {
    return { ok: false, code: "unauthorized" };
  }
  const apiUrl = process.env.NEXT_PUBLIC_API_URL;
  if (!apiUrl) {
    return { ok: false, code: "unavailable" };
  }

  let response: Response;
  try {
    response = await fetch(
      `${apiUrl.replace(/\/$/, "")}/attendance/schedules?date=${encodeURIComponent(date)}`,
      {
        headers: { Authorization: `Bearer ${accessToken}` },
        cache: "no-store",
      },
    );
  } catch (error) {
    console.error("Unable to reach the schedule API.", error);
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
    console.error("Schedule request failed with API status", response.status);
    return { ok: false, code: "unavailable" };
  }

  let body: unknown;
  try {
    body = await response.json();
  } catch (error) {
    console.error("The schedule API returned invalid JSON.", error);
    return { ok: false, code: "unavailable" };
  }
  if (
    !isObject(body) ||
    body.date !== date ||
    !Array.isArray(body.personnel) ||
    !Array.isArray(body.horaires)
  ) {
    console.error("The schedule API returned an invalid overview.");
    return { ok: false, code: "unavailable" };
  }

  const personnel: SchedulePerson[] = [];
  for (const item of body.personnel) {
    if (
      !isObject(item) ||
      !isUuid(item.id) ||
      typeof item.nom !== "string" ||
      typeof item.prenom !== "string" ||
      typeof item.email !== "string"
    ) {
      console.error("The schedule API returned an invalid personnel option.");
      return { ok: false, code: "unavailable" };
    }
    personnel.push({
      id: item.id,
      nom: item.nom,
      prenom: item.prenom,
      email: item.email,
    });
  }

  const horaires: ScheduleItem[] = [];
  for (const item of body.horaires) {
    if (
      !isObject(item) ||
      !isUuid(item.id) ||
      !isUuid(item.id_personnel) ||
      item.date !== date ||
      typeof item.heure_debut !== "string" ||
      !/^\d{2}:\d{2}(:\d{2})?$/.test(item.heure_debut) ||
      typeof item.heure_fin !== "string" ||
      !/^\d{2}:\d{2}(:\d{2})?$/.test(item.heure_fin) ||
      typeof item.type_activite !== "string" ||
      typeof item.nom !== "string" ||
      typeof item.prenom !== "string"
    ) {
      console.error("The schedule API returned an invalid schedule record.");
      return { ok: false, code: "unavailable" };
    }
    horaires.push({
      id: item.id,
      id_personnel: item.id_personnel,
      date: item.date,
      heure_debut: item.heure_debut.slice(0, 5),
      heure_fin: item.heure_fin.slice(0, 5),
      type_activite: item.type_activite,
      nom: item.nom,
      prenom: item.prenom,
    });
  }

  return { ok: true, personnel, horaires };
}

export async function saveSchedule(
  schedule: Omit<ScheduleItem, "id" | "nom" | "prenom">,
): Promise<SaveScheduleResult> {
  if (
    !isUuid(schedule.id_personnel) ||
    !/^\d{4}-\d{2}-\d{2}$/.test(schedule.date) ||
    !/^([01]\d|2[0-3]):[0-5]\d$/.test(schedule.heure_debut) ||
    !/^([01]\d|2[0-3]):[0-5]\d$/.test(schedule.heure_fin) ||
    schedule.heure_fin <= schedule.heure_debut ||
    typeof schedule.type_activite !== "string" ||
    schedule.type_activite.trim().length === 0 ||
    schedule.type_activite.trim().length > 120
  ) {
    return { ok: false, code: "invalid" };
  }

  const accessToken = await getAccessToken();
  if (!accessToken) {
    return { ok: false, code: "unauthorized" };
  }
  const apiUrl = process.env.NEXT_PUBLIC_API_URL;
  if (!apiUrl) {
    return { ok: false, code: "unavailable" };
  }

  let response: Response;
  try {
    response = await fetch(
      `${apiUrl.replace(/\/$/, "")}/attendance/schedules`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${accessToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          id_personnel: schedule.id_personnel,
          date: schedule.date,
          heure_debut: schedule.heure_debut,
          heure_fin: schedule.heure_fin,
          type_activite: schedule.type_activite.trim(),
        }),
        cache: "no-store",
      },
    );
  } catch (error) {
    console.error("Unable to reach the schedule API.", error);
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
    console.error("Saving schedule failed with API status", response.status);
    return { ok: false, code: "unavailable" };
  }
  return { ok: true };
}
