"use server";

import { createClient } from "@/lib/supabase/server";

export type DailyAttendanceInterval = {
  entree: string;
  sortie: string;
  dureeSecondes: number;
};

export type DailyAttendanceStatus =
  | "complete"
  | "incomplete"
  | "anomaly"
  | "incomplete_anomaly";

export type DailyAttendanceResult =
  | {
      ok: true;
      date: string;
      timezone: string;
      status: DailyAttendanceStatus;
      totalSeconds: number;
      eventCount: number;
      intervals: DailyAttendanceInterval[];
    }
  | {
      ok: false;
      code: "unauthorized" | "forbidden" | "unavailable" | "invalid";
    };

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isDailyAttendanceStatus(
  value: unknown,
): value is DailyAttendanceStatus {
  return (
    value === "complete" ||
    value === "incomplete" ||
    value === "anomaly" ||
    value === "incomplete_anomaly"
  );
}

export async function getDailyAttendance(
  requestedDate: string,
): Promise<DailyAttendanceResult> {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(requestedDate)) {
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
    response = await fetch(
      `${apiUrl.replace(/\/$/, "")}/attendance/me/daily-summary?date=${encodeURIComponent(requestedDate)}`,
      {
        headers: { Authorization: `Bearer ${session.access_token}` },
        cache: "no-store",
      },
    );
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
    console.error(
      "Daily attendance request failed with API status",
      response.status,
    );
    return { ok: false, code: "unavailable" };
  }

  let body: unknown;
  try {
    body = await response.json();
  } catch (error) {
    console.error("The attendance API returned invalid summary JSON.", error);
    return { ok: false, code: "unavailable" };
  }

  if (
    !isObject(body) ||
    body.date !== requestedDate ||
    body.fuseau_horaire !== "Africa/Casablanca" ||
    !isDailyAttendanceStatus(body.status) ||
    !Number.isSafeInteger(body.total_secondes) ||
    Number(body.total_secondes) < 0 ||
    !Number.isSafeInteger(body.event_count) ||
    Number(body.event_count) < 0 ||
    !Array.isArray(body.intervals)
  ) {
    console.error("The attendance API returned an invalid daily summary.");
    return { ok: false, code: "unavailable" };
  }

  const intervals: DailyAttendanceInterval[] = [];
  for (const interval of body.intervals) {
    if (
      !isObject(interval) ||
      typeof interval.entree !== "string" ||
      !Number.isFinite(Date.parse(interval.entree)) ||
      typeof interval.sortie !== "string" ||
      !Number.isFinite(Date.parse(interval.sortie)) ||
      !Number.isSafeInteger(interval.duree_secondes) ||
      Number(interval.duree_secondes) <= 0
    ) {
      console.error("The attendance API returned an invalid interval.");
      return { ok: false, code: "unavailable" };
    }
    intervals.push({
      entree: interval.entree,
      sortie: interval.sortie,
      dureeSecondes: Number(interval.duree_secondes),
    });
  }

  if (
    intervals.reduce((total, interval) => total + interval.dureeSecondes, 0) !==
    body.total_secondes
  ) {
    console.error("The attendance API returned inconsistent summary totals.");
    return { ok: false, code: "unavailable" };
  }

  return {
    ok: true,
    date: requestedDate,
    timezone: "Africa/Casablanca",
    status: body.status,
    totalSeconds: Number(body.total_secondes),
    eventCount: Number(body.event_count),
    intervals,
  };
}
