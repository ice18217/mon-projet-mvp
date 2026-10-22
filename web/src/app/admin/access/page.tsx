import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Suspense } from "react";

import { createClient } from "@/lib/supabase/server";
import { approveAccess, signOut } from "./actions";

export const metadata: Metadata = {
  title: "Approbation des accès — Pointage EIGSI",
};

type PendingPersonnel = {
  id: string;
  nom: string;
  prenom: string;
  email: string;
  type: string;
  created_at: string;
};

type AccessPageProps = {
  searchParams: Promise<{ result?: string }>;
};

const resultMessages: Record<string, string> = {
  approved: "L’accès a été approuvé.",
  configuration: "La configuration de l’API est incomplète.",
  failed: "L’approbation a échoué. Consultez les journaux du serveur.",
  forbidden: "Votre compte n’est pas autorisé à approuver des accès.",
  invalid: "La demande contient des informations invalides.",
  unavailable: "L’API est indisponible. Réessayez plus tard.",
};

export default function AccessApprovalPage(props: AccessPageProps) {
  return (
    <Suspense
      fallback={
        <main className="page">
          <section className="card">
            <p>Chargement des demandes d’accès…</p>
          </section>
        </main>
      }
    >
      <AccessApprovalContent {...props} />
    </Suspense>
  );
}

async function AccessApprovalContent({ searchParams }: AccessPageProps) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    redirect("/login");
  }

  const {
    data: { session },
  } = await supabase.auth.getSession();
  if (!session) {
    redirect("/login");
  }

  const apiUrl = process.env.NEXT_PUBLIC_API_URL;
  if (!apiUrl) {
    return (
      <AccessPageError message="La configuration de l’API est incomplète." />
    );
  }

  let response: Response;
  try {
    response = await fetch(`${apiUrl.replace(/\/$/, "")}/access/pending`, {
      headers: { Authorization: `Bearer ${session.access_token}` },
      cache: "no-store",
    });
  } catch (error) {
    console.error("Unable to reach the access-management API.", error);
    return (
      <AccessPageError message="L’API est indisponible. Réessayez plus tard." />
    );
  }

  if (response.status === 401) {
    redirect("/login");
  }
  if (response.status === 403) {
    return (
      <AccessPageError message="Cette page est réservée à l’administration technique approuvée." />
    );
  }
  if (!response.ok) {
    console.error(
      "Pending-access request failed with API status",
      response.status,
    );
    return (
      <AccessPageError message="Impossible de charger les demandes d’accès." />
    );
  }

  let pendingData: unknown;
  try {
    pendingData = await response.json();
  } catch (error) {
    console.error("The access-management API returned invalid JSON.", error);
    return <AccessPageError message="La réponse de l’API est invalide." />;
  }
  if (!Array.isArray(pendingData) || !pendingData.every(isPendingPersonnel)) {
    console.error(
      "The access-management API returned an invalid request list.",
    );
    return <AccessPageError message="La réponse de l’API est invalide." />;
  }
  const pendingPersonnel = pendingData;
  const { result } = await searchParams;

  return (
    <main className="page">
      <section aria-labelledby="access-title" className="card card-wide">
        <div className="header-row">
          <div>
            <p className="eyebrow">EIGSI Casablanca</p>
            <h1 id="access-title">Approbation des accès</h1>
          </div>
          <form action={signOut}>
            <button className="secondary-button" type="submit">
              Se déconnecter
            </button>
          </form>
        </div>

        {result && resultMessages[result] ? (
          <p
            aria-live="polite"
            className={result === "approved" ? "notice" : "error"}
          >
            {resultMessages[result]}
          </p>
        ) : null}

        {pendingPersonnel.length === 0 ? (
          <p>Aucune demande d’accès en attente.</p>
        ) : (
          <ul className="request-list">
            {pendingPersonnel.map((person) => (
              <li className="request-card" key={person.id}>
                <div>
                  <h2>
                    {person.prenom} {person.nom}
                  </h2>
                  <p>{person.email}</p>
                  <p>
                    Profil {person.type} · Demande du{" "}
                    {new Date(person.created_at).toLocaleDateString("fr-FR")}
                  </p>
                </div>
                <form action={approveAccess} className="approval-form">
                  <input name="personnel_id" type="hidden" value={person.id} />
                  <fieldset>
                    <legend>Rôles à attribuer</legend>
                    <label>
                      <input
                        defaultChecked
                        name="roles"
                        type="checkbox"
                        value="personnel"
                      />
                      Personnel
                    </label>
                    <label>
                      <input name="roles" type="checkbox" value="rh" />
                      RH
                    </label>
                    <label>
                      <input name="roles" type="checkbox" value="scolarite" />
                      Scolarité
                    </label>
                    <label>
                      <input name="roles" type="checkbox" value="finance" />
                      Finance
                    </label>
                  </fieldset>
                  <button type="submit">Approuver l’accès</button>
                </form>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}

function AccessPageError({ message }: { message: string }) {
  return (
    <main className="page">
      <section aria-labelledby="access-title" className="card">
        <p className="eyebrow">EIGSI Casablanca</p>
        <h1 id="access-title">Approbation des accès</h1>
        <p aria-live="polite" className="error">
          {message}
        </p>
      </section>
    </main>
  );
}

function isPendingPersonnel(value: unknown): value is PendingPersonnel {
  if (typeof value !== "object" || value === null) {
    return false;
  }

  return (
    "id" in value &&
    typeof value.id === "string" &&
    "nom" in value &&
    typeof value.nom === "string" &&
    "prenom" in value &&
    typeof value.prenom === "string" &&
    "email" in value &&
    typeof value.email === "string" &&
    "type" in value &&
    typeof value.type === "string" &&
    "created_at" in value &&
    typeof value.created_at === "string" &&
    Number.isFinite(Date.parse(value.created_at))
  );
}
