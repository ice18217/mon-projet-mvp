"use server";

import { redirect } from "next/navigation";

import { createClient } from "@/lib/supabase/server";

export type LoginState = {
  message?: string;
};

function getSafeNextPath(value: FormDataEntryValue | null): string {
  const hasControlCharacter =
    typeof value === "string" &&
    Array.from(value).some((character) => {
      const code = character.codePointAt(0);
      return code !== undefined && (code < 0x20 || code === 0x7f);
    });

  if (
    typeof value !== "string" ||
    !value.startsWith("/") ||
    value.startsWith("//") ||
    value.includes("\\") ||
    hasControlCharacter
  ) {
    return "/";
  }

  return value;
}

export async function signIn(
  _previousState: LoginState,
  formData: FormData,
): Promise<LoginState> {
  const email = formData.get("email");
  const password = formData.get("password");
  const nextPath = getSafeNextPath(formData.get("next"));

  if (
    typeof email !== "string" ||
    typeof password !== "string" ||
    !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim()) ||
    password.length === 0
  ) {
    return {
      message: "Saisissez une adresse e-mail et un mot de passe valides.",
    };
  }

  const supabase = await createClient();
  const { error } = await supabase.auth.signInWithPassword({
    email: email.trim(),
    password,
  });

  if (error) {
    return {
      message:
        "Connexion impossible. Vérifiez vos identifiants ou contactez l’administration.",
    };
  }

  redirect(nextPath);
}

export async function signOut(): Promise<void> {
  const supabase = await createClient();
  const { error } = await supabase.auth.signOut();

  if (error) {
    throw new Error("La déconnexion a échoué. Veuillez réessayer.");
  }

  redirect("/login");
}
