"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

export default function LoginForm() {
  const router = useRouter();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setError("");
    setLoading(true);
    const form = new FormData(event.currentTarget);
    try {
      const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          email: form.get("email"),
          password: form.get("password"),
        }),
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) {
        setError(body?.error?.message || "No se pudo iniciar sesión.");
        return;
      }
      router.push("/");
    } catch {
      setError("No se pudo conectar con el servidor. Comprueba tu conexión.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="chatly-auth">
      <section className="chatly-auth__brand">
        <div className="chatly-auth__wordmark-wrap">
          <span className="chatly-auth__wordmark">Chatly</span>
        </div>
      </section>
      <section className="chatly-auth__panel">
        <div className="chatly-auth__content">
          <h1 className="chatly-auth__title">Inicia sesión en Chatly</h1>
          <p className="chatly-auth__subtitle">
            Entra con tu correo y contraseña para chatear.
          </p>
          {error && <div className="chatly-auth__alert">{error}</div>}
          <form className="chatly-auth__stack chatly-auth__stack--wide" onSubmit={submit}>
            <label className="chatly-auth__stack chatly-auth__stack--tight">
              <span className="chatly-auth__label">Correo electrónico</span>
              <input
                autoComplete="email"
                className="chatly-auth__input"
                name="email"
                required
                type="email"
              />
            </label>
            <label className="chatly-auth__stack chatly-auth__stack--tight">
              <span className="chatly-auth__label">Tu contraseña</span>
              <input
                autoComplete="current-password"
                className="chatly-auth__input"
                name="password"
                required
                type="password"
              />
            </label>
            <button className="chatly-auth__button" disabled={loading} type="submit">
              {loading ? "Entrando…" : "Entrar"}
            </button>
          </form>
          <Link className="chatly-auth__link" href="/register">
            ¿No tienes cuenta? Crear una
          </Link>
          <Link className="chatly-auth__link" href="/forgot-password">
            ¿Olvidaste tu contraseña?
          </Link>
        </div>
      </section>
    </main>
  );
}
