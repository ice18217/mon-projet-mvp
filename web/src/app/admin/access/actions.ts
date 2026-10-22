"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { createClient } from "@/lib/supabase/server";

const allowedRoles = new Set(["personnel", "rh", "scolarite", "finance"]);

export async function approveAccess(formData: FormData): Promise<void> {
  const personnelId = formData.get("personnel_id");
  const roles = formData
    .getAll("roles")
    .filter((value): value is string => typeof value === "string");

  if (
    typeof personnelId !== "string" ||
    !/^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(
      personnelId,
    ) ||
    roles.length === 0 ||
    roles.some((role) => !allowedRoles.has(role)) ||
    new Set(roles).size !== roles.length
  ) {
    redirect("/admin/access?result=invalid");
  }

  const supabase = await createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session) {
    redirect("/login");
  }

  const apiUrl = process.env.NEXT_PUBLIC_API_URL;
  if (!apiUrl) {
    redirect("/admin/access?result=configuration");
  }

  let response: Response;
  try {
    response = await fetch(
      `${apiUrl.replace(/\/$/, "")}/access/${personnelId}/approve`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${session.access_token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ roles }),
        cache: "no-store",
      },
    );
  } catch (error) {
    console.error("Unable to reach the access-management API.", error);
    redirect("/admin/access?result=unavailable");
  }

  if (response.status === 403) {
    redirect("/admin/access?result=forbidden");
  }
  if (!response.ok) {
    console.error("Access approval failed with API status", response.status);
    redirect("/admin/access?result=failed");
  }

  revalidatePath("/admin/access");
  redirect("/admin/access?result=approved");
}

export async function signOut(): Promise<void> {
  const supabase = await createClient();
  const { error } = await supabase.auth.signOut();

  if (error) {
    throw new Error("La déconnexion a échoué. Veuillez réessayer.");
  }

  redirect("/login");
}
