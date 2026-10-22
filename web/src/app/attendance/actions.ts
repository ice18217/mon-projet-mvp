"use server";

import { createClient } from "@/lib/supabase/server";

export type AttendanceType = "entree" | "sortie";

export type AttendanceScanResult =
  | {
      ok: true;
      person: string;
      timestamp: string;
      type: AttendanceType;
      duplicate: boolean;
    }
  | {
      ok: false;
      code: "unauthorized" | "forbidden" | "invalid" | "unavailable";
    };

const uuidPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export async function recordAttendanceScan(
  payload: string,
  type: AttendanceType,
  idempotencyKey: string,
): Promise<AttendanceScanResult> {
  if (
    typeof payload !== "string" ||
    payload.length === 0 ||
    payload.length > 200 ||
    (type !== "entree" && type !== "sortie") ||
    !uuidPattern.test(idempotencyKey)
  ) {
    return { ok: false, code: "invalid" };
  }

  if (
    !process.env.NEXT_PUBLIC_SUPABASE_URL ||
    !process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
  ) {
    return { ok: false, code: "unavailable" };
  }

  const supabase = await createClient();
  const {
    data: { user },
    error: userError,
  } = await supabase.auth.getUser();
  if (userError || !user) {
    return { ok: false, code: "unauthorized" };
  }

  const {
    data: { session },
  } = await supabase.auth.getSession();
  if (!session) {
    return { ok: false, code: "unauthorized" };
  }

  const apiUrl = process.env.NEXT_PUBLIC_API_URL;
  if (!apiUrl) {
    return { ok: false, code: "unavailable" };
  }

  let response: Response;
  try {
    response = await fetch(`${apiUrl.replace(/\/$/, "")}/attendance/scan`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${session.access_token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        payload,
        type_pointage: type,
        idempotency_key: idempotencyKey,
      }),
      cache: "no-store",
    });
  } catch (error) {
    console.error("Unable to reach the attendance API.", error);
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
    console.error("Attendance scan failed with API status", response.status);
    return { ok: false, code: "unavailable" };
  }

  let result: unknown;
  try {
    result = await response.json();
  } catch (error) {
    console.error("The attendance API returned invalid scan JSON.", error);
    return { ok: false, code: "unavailable" };
  }
  if (
    typeof result !== "object" ||
    result === null ||
    !("nom" in result) ||
    typeof result.nom !== "string" ||
    !("prenom" in result) ||
    typeof result.prenom !== "string" ||
    !("date_heure" in result) ||
    typeof result.date_heure !== "string" ||
    !Number.isFinite(Date.parse(result.date_heure)) ||
    !("type_pointage" in result) ||
    (result.type_pointage !== "entree" && result.type_pointage !== "sortie") ||
    result.type_pointage !== type ||
    !("duplicate" in result) ||
    typeof result.duplicate !== "boolean"
  ) {
    console.error("The attendance API returned an invalid scan result.");
    return { ok: false, code: "unavailable" };
  }

  return {
    ok: true,
    person: `${result.prenom} ${result.nom}`,
    timestamp: result.date_heure,
    type: result.type_pointage,
    duplicate: result.duplicate,
  };
}
