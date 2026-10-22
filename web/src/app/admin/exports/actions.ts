"use server";

import { createClient } from "@/lib/supabase/server";

export type PayrollExportResult =
  | { ok: true; csv: string }
  | {
      ok: false;
      code: "unauthorized" | "forbidden" | "invalid" | "unavailable";
    };

function isWeekStart(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    return false;
  }
  const parsed = new Date(`${value}T00:00:00Z`);
  return (
    Number.isFinite(parsed.getTime()) &&
    parsed.toISOString().slice(0, 10) === value &&
    parsed.getUTCDay() === 1
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

export async function downloadWeeklyPayrollExport(
  weekStart: string,
): Promise<PayrollExportResult> {
  if (!isWeekStart(weekStart)) {
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
      `${apiUrl.replace(/\/$/, "")}/payroll/weekly-export?week_start=${encodeURIComponent(weekStart)}`,
      {
        headers: { Authorization: `Bearer ${token}` },
        cache: "no-store",
      },
    );
  } catch (error) {
    console.error("Unable to reach the weekly payroll-export API.", error);
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
      "Weekly payroll-export request failed with API status",
      response.status,
    );
    return { ok: false, code: "unavailable" };
  }

  if (!response.headers.get("content-type")?.startsWith("text/csv")) {
    console.error("The weekly payroll-export API did not return a CSV file.");
    return { ok: false, code: "unavailable" };
  }
  try {
    const csv = await response.text();
    if (!csv.startsWith("\uFEFF")) {
      console.error("The weekly payroll-export API returned an invalid CSV.");
      return { ok: false, code: "unavailable" };
    }
    return { ok: true, csv };
  } catch (error) {
    console.error("Unable to read the weekly payroll-export CSV.", error);
    return { ok: false, code: "unavailable" };
  }
}
