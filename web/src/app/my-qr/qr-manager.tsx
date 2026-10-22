"use client";

import Image from "next/image";
import { useEffect, useState } from "react";

import { getMyQrStatus, issueMyQr } from "./actions";

export function QRManager() {
  const [hasActiveQr, setHasActiveQr] = useState<boolean | null>(null);
  const [image, setImage] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [issuing, setIssuing] = useState(false);

  useEffect(() => {
    let cancelled = false;

    void getMyQrStatus().then((result) => {
      if (cancelled) {
        return;
      }
      if (result.ok) {
        setHasActiveQr(result.hasActiveCredential);
      } else {
        setMessage(result.message);
      }
      setLoading(false);
    });

    return () => {
      cancelled = true;
    };
  }, []);

  async function createQr() {
    setIssuing(true);
    setMessage(null);
    const result = await issueMyQr();
    if (result.ok) {
      setImage(result.image);
      setHasActiveQr(true);
    } else {
      setMessage(result.message);
    }
    setIssuing(false);
  }

  return (
    <section className="card qr-card" aria-labelledby="qr-title">
      <p className="eyebrow">EIGSI Casablanca</p>
      <h1 id="qr-title">Mon QR de pointage</h1>
      <p>
        Présentez ce QR à l’opérateur RH/Scolarité sur l’appareil de pointage.
        Il ne contient pas votre nom ni votre adresse e-mail.
      </p>

      {loading ? <p aria-live="polite">Vérification du QR…</p> : null}
      {message ? (
        <p aria-live="polite" className="error">
          {message}
        </p>
      ) : null}

      {!loading && hasActiveQr && !image ? (
        <p className="notice">
          Un QR est déjà actif. Pour l’afficher à nouveau, créez-en un nouveau;
          l’ancien sera immédiatement invalidé.
        </p>
      ) : null}

      {image ? (
        <div className="qr-display">
          <Image
            alt="Votre QR code personnel de pointage"
            height={512}
            src={image}
            unoptimized
            width={512}
          />
          <a
            className="button-link"
            download="eigsi-qr-pointage.png"
            href={image}
          >
            Télécharger le QR (PNG)
          </a>
          <p className="hint">
            Gardez cette image privée. Si elle est perdue ou partagée,
            générez-en une nouvelle pour invalider l’ancienne.
          </p>
        </div>
      ) : null}

      {!loading && hasActiveQr !== null ? (
        <button disabled={issuing} onClick={createQr} type="button">
          {issuing
            ? "Création en cours…"
            : hasActiveQr
              ? "Révoquer et créer un nouveau QR"
              : "Créer mon QR"}
        </button>
      ) : null}
    </section>
  );
}
