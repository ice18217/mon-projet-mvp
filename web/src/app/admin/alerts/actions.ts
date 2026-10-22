"use server";

import { createClient } from "@/lib/supabase/server";

export type AlertItem = {
  id: string;
  id_personnel: string;
  id_emploi_du_temps: string;
  date_alerte: string;
  type: "absence" | "retard";
  statut: "envoyee" | "traitee";
  nom: string;
  prenom: string;
  debut: string;
  fin: string;
  type_activite: string;
};

export type AlertListResult =
  | { ok: true; thresholdMinutes: number; alerts: AlertItem[] }
  | {
      ok: false;
      code: "unauthorized" | "forbidden" | "unavailable" | "invalid";
    };

export type ResolveAlertResult =
  | { ok: true }
  | {
      ok: false;
      code: "unauthorized" | "forbidden" | "unavailable" | "invalid";
    };

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

export async function getDailyAlerts(date: string): Promise<AlertListResult> {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) {
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
      `${apiUrl.replace(/\/$/, "")}/attendance/alerts?date=${encodeURIComponent(date)}`,
      {
        headers: { Authorization: `Bearer ${token}` },
        cache: "no-store",
      },
    );
  } catch (error) {
    console.error("Unable to reach the attendance-alert API.", error);
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
    console.error("Alert listing failed with API status", response.status);
    return { ok: false, code: "unavailable" };
  }

  let body: unknown;
  try {
    body = await response.json();
  } catch (error) {
    console.error("The alert API returned invalid JSON.", error);
    return { ok: false, code: "unavailable" };
  }
  if (
    !isObject(body) ||
    body.date !== date ||
    !Number.isSafeInteger(body.seuil_retard_minutes) ||
    !Array.isArray(body.alertes)
  ) {
    console.error("The alert API returned an invalid alert list.");
    return { ok: false, code: "unavailable" };
  }

  const alerts: AlertItem[] = [];
  for (const value of body.alertes) {
    if (
      !isObject(value) ||
      !isUuid(value.id) ||
      !isUuid(value.id_personnel) ||
      !isUuid(value.id_emploi_du_temps) ||
      typeof value.date_alerte !== "string" ||
      !Number.isFinite(Date.parse(value.date_alerte)) ||
      (value.type !== "absence" && value.type !== "retard") ||
      (value.statut !== "envoyee" && value.statut !== "traitee") ||
      typeof value.nom !== "string" ||
      typeof value.prenom !== "string" ||
      typeof value.debut !== "string" ||
      !Number.isFinite(Date.parse(value.debut)) ||
      typeof value.fin !== "string" ||
      !Number.isFinite(Date.parse(value.fin)) ||
      typeof value.type_activite !== "string"
    ) {
      console.error("The alert API returned an invalid alert record.");
      return { ok: false, code: "unavailable" };
    }
    alerts.push({
      id: value.id,
      id_personnel: value.id_personnel,
      id_emploi_du_temps: value.id_emploi_du_temps,
      date_alerte: value.date_alerte,
      type: value.type,
      statut: value.statut,
      nom: value.nom,
      prenom: value.prenom,
      debut: value.debut,
      fin: value.fin,
      type_activite: value.type_activite,
    });
  }

  return {
    ok: true,
    thresholdMinutes: Number(body.seuil_retard_minutes),
    alerts,
  };
}

export async function resolveAlert(
  alertId: string,
): Promise<ResolveAlertResult> {
  if (!isUuid(alertId)) {
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
      `${apiUrl.replace(/\/$/, "")}/attendance/alerts/${alertId}/resolve`,
      {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        cache: "no-store",
      },
    );
  } catch (error) {
    console.error("Unable to reach the attendance-alert API.", error);
    return { ok: false, code: "unavailable" };
  }
  if (response.status === 401) {
    return { ok: false, code: "unauthorized" };
  }
  if (response.status === 403) {
    return { ok: false, code: "forbidden" };
  }
  if (response.status === 404) {
    return { ok: false, code: "invalid" };
  }
  if (!response.ok) {
    console.error("Resolving alert failed with API status", response.status);
    return { ok: false, code: "unavailable" };
  }
  return { ok: true };
}
