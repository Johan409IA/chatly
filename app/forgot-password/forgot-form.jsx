"use client";

import { useState } from "react";
import Link from "next/link";

export default function ForgotPasswordForm() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [sent, setSent] = useState(false);
  const [loading, setLoading] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      const response = await fetch("/api/auth/forgot-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) {
        setError(body?.error?.message || "No se pudo solicitar la recuperación.");
        return;
      }
      setSent(true);
    } catch {
      setError("No se pudo conectar con el servidor. Comprueba tu conexión.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      {error && <div className="chatly-auth__alert">{error}</div>}
      {sent ? (
        <div className="chatly-auth__alert chatly-auth__alert--info">
          Si el correo está registrado, te enviaremos un enlace para restablecer la contraseña.
        </div>
      ) : (
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
            {loading ? "Enviando…" : "Enviar enlace"}
          </button>
        </form>
      )}
      <Link className="chatly-auth__link" href="/login">
        Volver a iniciar sesión
      </Link>
    </>
  );
}
