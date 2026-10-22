"use server";

import { createClient } from "@/lib/supabase/server";

export type CorrectionHistoryEntry = {
  revision: number;
  date_correction: string;
  motif: string;
  ancienne_valeur: string;
  nouvelle_valeur: string;
};

export type AttendancePointageCorrection = {
  id_pointage: string;
  id_personnel: string;
  type_pointage: "entree" | "sortie";
  date_heure_originale: string;
  date_heure_effective: string;
  historique: CorrectionHistoryEntry[];
  nom: string;
  prenom: string;
};

export type AttendanceCorrectionsResult =
  | { ok: true; date: string; pointages: AttendancePointageCorrection[] }
  | {
      ok: false;
      code: "unauthorized" | "forbidden" | "unavailable" | "invalid";
    };

export type SaveCorrectionResult =
  | { ok: true }
  | {
      ok: false;
      code: "unauthorized" | "forbidden" | "unavailable" | "invalid";
    };

type CorrectionErrorCode = Exclude<SaveCorrectionResult, { ok: true }>["code"];
type RequestFailure = { ok: false; code: CorrectionErrorCode };

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

function isTimestamp(value: unknown): value is string {
  return typeof value === "string" && Number.isFinite(Date.parse(value));
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

function parseHistoryEntry(value: unknown): CorrectionHistoryEntry | null {
  if (
    !isObject(value) ||
    !Number.isSafeInteger(value.revision) ||
    (value.revision as number) < 1 ||
    !isTimestamp(value.date_correction) ||
    typeof value.motif !== "string" ||
    !isTimestamp(value.ancienne_valeur) ||
    !isTimestamp(value.nouvelle_valeur)
  ) {
    return null;
  }
  return {
    revision: value.revision as number,
    date_correction: value.date_correction,
    motif: value.motif,
    ancienne_valeur: value.ancienne_valeur,
    nouvelle_valeur: value.nouvelle_valeur,
  };
}

function parsePointage(value: unknown): AttendancePointageCorrection | null {
  if (
    !isObject(value) ||
    !isUuid(value.id_pointage) ||
    !isUuid(value.id_personnel) ||
    (value.type_pointage !== "entree" && value.type_pointage !== "sortie") ||
    !isTimestamp(value.date_heure_originale) ||
    !isTimestamp(value.date_heure_effective) ||
    !Array.isArray(value.historique) ||
    typeof value.nom !== "string" ||
    typeof value.prenom !== "string"
  ) {
    return null;
  }
  const history: CorrectionHistoryEntry[] = [];
  for (const item of value.historique) {
    const entry = parseHistoryEntry(item);
    if (!entry) {
      return null;
    }
    history.push(entry);
  }
  return {
    id_pointage: value.id_pointage,
    id_personnel: value.id_personnel,
    type_pointage: value.type_pointage,
    date_heure_originale: value.date_heure_originale,
    date_heure_effective: value.date_heure_effective,
    historique: history,
    nom: value.nom,
    prenom: value.prenom,
  };
}

function classifyStatus(status: number): CorrectionErrorCode {
  if (status === 401) return "unauthorized";
  if (status === 403) return "forbidden";
  if (status === 422 || status === 404) return "invalid";
  return "unavailable";
}

async function authenticatedRequest(
  path: string,
  init: RequestInit,
): Promise<Response | RequestFailure> {
  const token = await getAccessToken();
  if (!token) {
    return { ok: false, code: "unauthorized" };
  }
  const apiUrl = process.env.NEXT_PUBLIC_API_URL;
  if (!apiUrl) {
    return { ok: false, code: "unavailable" };
  }
  try {
    return await fetch(`${apiUrl.replace(/\/$/, "")}${path}`, {
      ...init,
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      cache: "no-store",
    });
  } catch (error) {
    console.error("Unable to reach the attendance-corrections API.", error);
    return { ok: false, code: "unavailable" };
  }
}

export async function getAttendanceCorrections(
  date: string,
): Promise<AttendanceCorrectionsResult> {
  if (!isValidDate(date)) {
    return { ok: false, code: "invalid" };
  }
  const response = await authenticatedRequest(
    `/attendance/corrections?date=${encodeURIComponent(date)}`,
    { method: "GET" },
  );
  if (!("status" in response)) {
    return response;
  }
  if (!response.ok) {
    console.error(
      "Attendance-corrections request failed with API status",
      response.status,
    );
    return { ok: false, code: classifyStatus(response.status) };
  }
  let body: unknown;
  try {
    body = await response.json();
  } catch (error) {
    console.error(
      "The attendance-corrections API returned invalid JSON.",
      error,
    );
    return { ok: false, code: "unavailable" };
  }
  if (
    !isObject(body) ||
    body.date !== date ||
    body.fuseau_horaire !== "Africa/Casablanca" ||
    !Array.isArray(body.pointages)
  ) {
    console.error(
      "The attendance-corrections API returned an invalid response.",
    );
    return { ok: false, code: "unavailable" };
  }
  const pointages: AttendancePointageCorrection[] = [];
  for (const item of body.pointages) {
    const pointage = parsePointage(item);
    if (!pointage) {
      console.error(
        "The attendance-corrections API returned an invalid attendance event.",
      );
      return { ok: false, code: "unavailable" };
    }
    pointages.push(pointage);
  }
  return { ok: true, date, pointages };
}

export async function saveAttendanceCorrection(
  pointageId: string,
  date: string,
  heure: string,
  motif: string,
): Promise<SaveCorrectionResult> {
  if (
    !isUuid(pointageId) ||
    !isValidDate(date) ||
    !/^([01]\d|2[0-3]):[0-5]\d$/.test(heure) ||
    motif.trim().length < 5 ||
    motif.trim().length > 500
  ) {
    return { ok: false, code: "invalid" };
  }
  const response = await authenticatedRequest(
    `/attendance/corrections/${encodeURIComponent(pointageId)}`,
    {
      method: "POST",
      body: JSON.stringify({ date, heure, motif: motif.trim() }),
    },
  );
  if (!("status" in response)) {
    return response;
  }
  if (response.status === 204) {
    return { ok: true };
  }
  console.error(
    "Attendance-correction write failed with API status",
    response.status,
  );
  return { ok: false, code: classifyStatus(response.status) };
}
