"use client";

import { useState } from "react";
import Link from "next/link";

function isStrongPassword(value) {
  return (
    value.length >= 8 &&
    /[A-Z]/.test(value) &&
    /[a-z]/.test(value) &&
    /[^a-zA-Z0-9]/.test(value)
  );
}

export default function ResetPasswordForm({ tokenHash }) {
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setError("");
    if (!tokenHash) {
      setError("El enlace no es válido o ha caducado.");
      return;
    }
    if (!isStrongPassword(password)) {
      setError("La contraseña necesita 8 caracteres, una mayúscula, una minúscula y un símbolo.");
      return;
    }
    if (password !== confirmation) {
      setError("Las contraseñas no coinciden.");
      return;
    }
    setLoading(true);
    try {
      const response = await fetch("/api/auth/reset-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token_hash: tokenHash, password }),
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) {
        setError(body?.error?.message || "No se pudo cambiar la contraseña.");
        return;
      }
      setSuccess(true);
    } catch {
      setError("No se pudo conectar con el servidor. Comprueba tu conexión.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      {error && <div className="chatly-auth__alert">{error}</div>}
      {success ? (
        <>
          <div className="chatly-auth__alert chatly-auth__alert--info">
            La contraseña se cambió. Ya puedes iniciar sesión.
          </div>
          <Link className="chatly-auth__link" href="/login">
            Ir a iniciar sesión
          </Link>
        </>
      ) : (
        <form className="chatly-auth__stack chatly-auth__stack--wide" onSubmit={submit}>
          <label className="chatly-auth__stack chatly-auth__stack--tight">
            <span className="chatly-auth__label">Nueva contraseña</span>
            <input
              autoComplete="new-password"
              className="chatly-auth__input"
              onChange={(event) => setPassword(event.target.value)}
              required
              type="password"
              value={password}
            />
          </label>
          <label className="chatly-auth__stack chatly-auth__stack--tight">
            <span className="chatly-auth__label">Confirma la contraseña</span>
            <input
              autoComplete="new-password"
              className="chatly-auth__input"
              onChange={(event) => setConfirmation(event.target.value)}
              required
              type="password"
              value={confirmation}
            />
          </label>
          <button className="chatly-auth__button" disabled={loading} type="submit">
            {loading ? "Guardando…" : "Cambiar contraseña"}
          </button>
        </form>
      )}
    </>
  );
}
