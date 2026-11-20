"use client";

import { useState } from "react";
import Link from "next/link";

export default function ResendForm({ initialEmail }) {
  const [email, setEmail] = useState(initialEmail);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setError("");
    setInfo("");
    setLoading(true);
    try {
      const response = await fetch("/api/auth/resend-verification", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) {
        setError(body?.error?.message || "No se pudo enviar el correo.");
        return;
      }
      setInfo("Si el correo está registrado, te enviaremos otro enlace.");
    } catch {
      setError("No se pudo conectar con el servidor. Comprueba tu conexión.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <p className="chatly-auth__subtitle">
        Si no ves el mensaje, revisa la carpeta de spam o solicita otro.
      </p>
      {error && <div className="chatly-auth__alert">{error}</div>}
      {info && <div className="chatly-auth__alert chatly-auth__alert--info">{info}</div>}
      <form className="chatly-auth__stack chatly-auth__stack--wide" onSubmit={submit}>
        <label className="chatly-auth__stack chatly-auth__stack--tight">
          <span className="chatly-auth__label">Correo electrónico</span>
          <input
            autoComplete="email"
            className="chatly-auth__input"
            onChange={(event) => setEmail(event.target.value)}
            required
            type="email"
            value={email}
          />
        </label>
        <button className="chatly-auth__button" disabled={loading} type="submit">
          {loading ? "Enviando…" : "Reenviar correo"}
        </button>
      </form>
      <Link className="chatly-auth__link" href="/login">
        Volver a iniciar sesión
      </Link>
    </>
  );
}
