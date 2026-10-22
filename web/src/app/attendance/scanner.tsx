"use client";

import { BrowserQRCodeReader } from "@zxing/browser";
import { useEffect, useRef, useState } from "react";

import {
  type AttendanceScanResult,
  type AttendanceType,
  recordAttendanceScan,
} from "./actions";

const errorMessages = {
  unauthorized: "Votre session a expiré. Reconnectez-vous.",
  forbidden: "Cette fonction est réservée aux comptes RH/Scolarité approuvés.",
  invalid: "QR invalide, révoqué ou non reconnu. Aucun pointage n’a été créé.",
  unavailable:
    "Le pointage n’a pas pu être confirmé. Vérifiez l’API puis réessayez.",
} as const;

export function AttendanceScanner() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const controlsRef = useRef<{ stop: () => void } | null>(null);
  const handlingScanRef = useRef(false);
  const [type, setType] = useState<AttendanceType | "">("");
  const [scanning, setScanning] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [result, setResult] = useState<AttendanceScanResult | null>(null);

  useEffect(
    () => () => {
      controlsRef.current?.stop();
    },
    [],
  );

  async function startScanner() {
    if (!videoRef.current || !type) {
      return;
    }

    setMessage(null);
    setResult(null);
    setScanning(true);
    const reader = new BrowserQRCodeReader();

    try {
      const controls = await reader.decodeFromVideoDevice(
        undefined,
        videoRef.current,
        (decoded, _error, activeControls) => {
          if (!decoded || !type || handlingScanRef.current) {
            return;
          }
          handlingScanRef.current = true;
          controlsRef.current = activeControls;
          activeControls.stop();
          controlsRef.current = null;
          setScanning(false);
          setSubmitting(true);
          void recordAttendanceScan(
            decoded.getText(),
            type,
            crypto.randomUUID(),
          )
            .then((scanResult) => {
              setResult(scanResult);
              if (!scanResult.ok) {
                setMessage(errorMessages[scanResult.code]);
              }
            })
            .finally(() => {
              handlingScanRef.current = false;
              setSubmitting(false);
            });
        },
      );
      if (!handlingScanRef.current) {
        controlsRef.current = controls;
      }
    } catch (error) {
      console.error("Unable to start the QR camera.", error);
      controlsRef.current?.stop();
      controlsRef.current = null;
      handlingScanRef.current = false;
      setScanning(false);
      setMessage(
        "Impossible d’ouvrir la caméra. Autorisez son accès et utilisez HTTPS ou localhost.",
      );
    }
  }

  function stopScanner() {
    controlsRef.current?.stop();
    controlsRef.current = null;
    setScanning(false);
  }

  return (
    <section className="card scanner-card" aria-labelledby="attendance-title">
      <p className="eyebrow">EIGSI Casablanca</p>
      <h1 id="attendance-title">Pointage par QR</h1>
      <p>
        Sélectionnez le type d’événement avant chaque scan. L’heure est
        enregistrée par le serveur.
      </p>

      <fieldset className="event-choice">
        <legend>Type de pointage</legend>
        <label>
          <input
            checked={type === "entree"}
            disabled={scanning || submitting}
            name="type-pointage"
            onChange={() => setType("entree")}
            type="radio"
          />
          Entrée
        </label>
        <label>
          <input
            checked={type === "sortie"}
            disabled={scanning || submitting}
            name="type-pointage"
            onChange={() => setType("sortie")}
            type="radio"
          />
          Sortie
        </label>
      </fieldset>

      <video
        aria-label="Aperçu de la caméra de pointage"
        className="scanner-video"
        muted
        playsInline
        ref={videoRef}
      />

      {message ? (
        <p aria-live="assertive" className="error">
          {message}
        </p>
      ) : null}
      {result?.ok ? (
        <div aria-live="polite" className="notice">
          <strong>
            {result.duplicate
              ? "Pointage déjà enregistré"
              : "Pointage enregistré"}
          </strong>
          <p>
            {result.person} — {result.type === "entree" ? "Entrée" : "Sortie"}
          </p>
          <p>
            {new Date(result.timestamp).toLocaleString("fr-FR", {
              dateStyle: "short",
              timeStyle: "medium",
              timeZone: "Africa/Casablanca",
            })}
          </p>
        </div>
      ) : null}

      {scanning ? (
        <button
          className="secondary-button"
          onClick={stopScanner}
          type="button"
        >
          Arrêter la caméra
        </button>
      ) : (
        <button
          disabled={!type || submitting}
          onClick={startScanner}
          type="button"
        >
          {submitting
            ? "Enregistrement du pointage…"
            : result?.ok
              ? "Nouveau scan"
              : "Démarrer le scanner"}
        </button>
      )}
      <p className="hint">
        Le scanner s’arrête après chaque lecture. Vérifiez le résultat avant de
        lancer un nouveau scan.
      </p>
    </section>
  );
}
