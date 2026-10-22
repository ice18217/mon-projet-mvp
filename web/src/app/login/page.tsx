import type { Metadata } from "next";
import { Suspense } from "react";

import { LoginForm } from "./login-form";

export const metadata: Metadata = {
  title: "Connexion — Pointage EIGSI",
};

type LoginPageProps = {
  searchParams: Promise<{ next?: string | string[] }>;
};

export default function LoginPage(props: LoginPageProps) {
  return (
    <Suspense
      fallback={
        <main className="page">
          <section className="card">
            <p>Chargement de la connexion…</p>
          </section>
        </main>
      }
    >
      <LoginPageContent {...props} />
    </Suspense>
  );
}

async function LoginPageContent({ searchParams }: LoginPageProps) {
  const { next } = await searchParams;

  return (
    <main className="page">
      <section aria-labelledby="login-title" className="card">
        <p className="eyebrow">EIGSI Casablanca</p>
        <h1 id="login-title">Se connecter</h1>
        <p>Accédez à la plateforme de suivi des présences du personnel.</p>
        <LoginForm next={typeof next === "string" ? next : ""} />
      </section>
    </main>
  );
}
