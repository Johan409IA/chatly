"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

export default function ConfirmStatus({ tokenHash, code, type }) {
  const [message, setMessage] = useState("Validando el enlace…");
  const [error, setError] = useState(false);

  useEffect(() => {
    const hash = new URLSearchParams(window.location.hash.replace(/^#/, ""));
    const resolvedTokenHash = tokenHash || hash.get("token_hash") || "";
    const resolvedCode = code || hash.get("code") || "";
    fetch("/api/auth/confirm", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        token_hash: resolvedTokenHash || undefined,
        code: resolvedCode || undefined,
        type,
      }),
    })
      .then(async (response) => {
        const body = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(body?.error?.message || "No se pudo confirmar el correo.");
        setMessage("Correo confirmado. Ya puedes iniciar sesión.");
      })
      .catch((cause) => {
        setError(true);
        setMessage(cause.message);
      });
  }, [tokenHash, code, type]);

  return (
    <>
      <div className={error ? "chatly-auth__alert" : "chatly-auth__alert chatly-auth__alert--info"}>
        {message}
      </div>
      <Link className="chatly-auth__link" href="/login">
        Ir a iniciar sesión
      </Link>
    </>
  );
}
