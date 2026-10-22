"use server";

import { createClient } from "@/lib/supabase/server";

export type QRStatusResult =
  | { ok: true; hasActiveCredential: boolean }
  | { ok: false; message: string };

export type QRIssueResult =
  | { ok: true; image: string }
  | { ok: false; message: string };

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

function getApiUrl(): string | null {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL;
  return apiUrl ? apiUrl.replace(/\/$/, "") : null;
}

export async function getMyQrStatus(): Promise<QRStatusResult> {
  if (
    !process.env.NEXT_PUBLIC_SUPABASE_URL ||
    !process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
  ) {
    return { ok: false, message: "L’authentification n’est pas configurée." };
  }
  const accessToken = await getAccessToken();
  if (!accessToken) {
    return { ok: false, message: "Reconnectez-vous pour accéder à votre QR." };
  }

  const apiUrl = getApiUrl();
  if (!apiUrl) {
    return { ok: false, message: "La configuration de l’API est incomplète." };
  }

  let response: Response;
  try {
    response = await fetch(`${apiUrl}/attendance/qr/me`, {
      headers: { Authorization: `Bearer ${accessToken}` },
      cache: "no-store",
    });
  } catch (error) {
    console.error("Unable to reach the attendance API.", error);
    return {
      ok: false,
      message: "L’API est indisponible. Réessayez plus tard.",
    };
  }

  if (response.status === 401) {
    return { ok: false, message: "Reconnectez-vous pour accéder à votre QR." };
  }
  if (response.status === 403) {
    return {
      ok: false,
      message: "Votre compte n’est pas autorisé à créer un QR personnel.",
    };
  }
  if (!response.ok) {
    console.error("QR status request failed with API status", response.status);
    return { ok: false, message: "Impossible de vérifier votre QR." };
  }

  let result: unknown;
  try {
    result = await response.json();
  } catch (error) {
    console.error("The attendance API returned invalid QR status JSON.", error);
    return { ok: false, message: "La réponse de l’API est invalide." };
  }
  if (
    typeof result !== "object" ||
    result === null ||
    !("has_active_credential" in result) ||
    typeof result.has_active_credential !== "boolean"
  ) {
    console.error("The attendance API returned an invalid QR status.");
    return { ok: false, message: "La réponse de l’API est invalide." };
  }

  return { ok: true, hasActiveCredential: result.has_active_credential };
}

export async function issueMyQr(): Promise<QRIssueResult> {
  if (
    !process.env.NEXT_PUBLIC_SUPABASE_URL ||
    !process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
  ) {
    return { ok: false, message: "L’authentification n’est pas configurée." };
  }
  const accessToken = await getAccessToken();
  if (!accessToken) {
    return { ok: false, message: "Reconnectez-vous pour créer votre QR." };
  }

  const apiUrl = getApiUrl();
  if (!apiUrl) {
    return { ok: false, message: "La configuration de l’API est incomplète." };
  }

  let response: Response;
  try {
    response = await fetch(`${apiUrl}/attendance/qr/me`, {
      method: "POST",
      headers: { Authorization: `Bearer ${accessToken}` },
      cache: "no-store",
    });
  } catch (error) {
    console.error("Unable to reach the attendance API.", error);
    return {
      ok: false,
      message: "L’API est indisponible. Réessayez plus tard.",
    };
  }

  if (response.status === 401) {
    return { ok: false, message: "Reconnectez-vous pour créer votre QR." };
  }
  if (response.status === 403) {
    return {
      ok: false,
      message: "Votre compte n’est pas autorisé à créer un QR personnel.",
    };
  }
  if (!response.ok) {
    console.error("QR issuance failed with API status", response.status);
    return { ok: false, message: "La création du QR a échoué." };
  }

  let result: unknown;
  try {
    result = await response.json();
  } catch (error) {
    console.error("The attendance API returned invalid QR image JSON.", error);
    return { ok: false, message: "La réponse de l’API est invalide." };
  }
  if (
    typeof result !== "object" ||
    result === null ||
    !("qr_image" in result) ||
    typeof result.qr_image !== "string" ||
    !result.qr_image.startsWith("data:image/png;base64,")
  ) {
    console.error("The attendance API returned an invalid QR image.");
    return { ok: false, message: "La réponse de l’API est invalide." };
  }

  return { ok: true, image: result.qr_image };
}
