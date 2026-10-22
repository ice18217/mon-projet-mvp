"use client";

import { useActionState } from "react";

import { type LoginState, signIn } from "./actions";

const initialState: LoginState = {};

export function LoginForm({ next }: { next: string }) {
  const [state, action, pending] = useActionState(signIn, initialState);

  return (
    <form action={action} className="form">
      <input name="next" type="hidden" value={next} />
      <label htmlFor="email">Adresse e-mail</label>
      <input
        autoComplete="username"
        id="email"
        name="email"
        required
        type="email"
      />
      <label htmlFor="password">Mot de passe</label>
      <input
        autoComplete="current-password"
        id="password"
        minLength={1}
        name="password"
        required
        type="password"
      />
      {state.message ? (
        <p aria-live="polite" className="error">
          {state.message}
        </p>
      ) : null}
      <button disabled={pending} type="submit">
        {pending ? "Connexion…" : "Se connecter"}
      </button>
      <p className="hint">
        Les comptes sont créés et approuvés par l’administration technique.
      </p>
    </form>
  );
}
