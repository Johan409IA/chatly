"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

const aliasPattern = /^[a-z][a-z0-9_]{2,19}$/;

function isStrongPassword(value) {
  return (
    value.length >= 8 &&
    /[A-Z]/.test(value) &&
    /[a-z]/.test(value) &&
    /[^a-zA-Z0-9]/.test(value)
  );
}

function ageIsAllowed(value) {
  if (!value) return false;
  const birth = new Date(`${value}T00:00:00Z`);
  if (Number.isNaN(birth.getTime()) || birth.toISOString().slice(0, 10) !== value) {
    return false;
  }
  const today = new Date();
  let age = today.getUTCFullYear() - birth.getUTCFullYear();
  if (
    today.getUTCMonth() < birth.getUTCMonth() ||
    (today.getUTCMonth() === birth.getUTCMonth() &&
      today.getUTCDate() < birth.getUTCDate())
  ) {
    age -= 1;
  }
  return age >= 18 && age <= 120;
}

export default function RegisterForm() {
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [values, setValues] = useState({
    display_name: "",
    email: "",
    alias: "",
    password: "",
    password_confirm: "",
    birth_date: "",
    gender: "",
  });
  const [catalog, setCatalog] = useState([]);
  const [interestIds, setInterestIds] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [catalogLoaded, setCatalogLoaded] = useState(false);

  useEffect(() => {
    if (step !== 5 || catalogLoaded) return;
    fetch("/api/interests")
      .then(async (response) => {
        const body = await response.json();
        if (!response.ok) throw new Error(body?.error?.message || "No se pudo cargar el catálogo.");
        setCatalog(body);
        setCatalogLoaded(true);
      })
      .catch((cause) => {
        setError(cause.message);
        setCatalogLoaded(true);
      });
  }, [step, catalogLoaded]);

  function change(field, value) {
    setValues((current) => ({ ...current, [field]: value }));
  }

  function validateStep() {
    if (step === 1 && values.display_name.trim().length < 2) {
      return "Escribe tu nombre para continuar.";
    }
    if (step === 2) {
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(values.email.trim())) {
        return "Escribe un correo válido.";
      }
      if (!aliasPattern.test(values.alias.trim().toLowerCase())) {
        return "El alias debe tener 3–20 caracteres: letra inicial y luego letras, números o _.";
      }
    }
    if (step === 3) {
      if (!isStrongPassword(values.password)) {
        return "La contraseña necesita 8 caracteres, una mayúscula, una minúscula y un símbolo.";
      }
      if (values.password !== values.password_confirm) {
        return "Las contraseñas no coinciden.";
      }
    }
    if (step === 4 && (!ageIsAllowed(values.birth_date) || !values.gender)) {
      return "Debes tener entre 18 y 120 años y elegir una opción de género.";
    }
    return "";
  }

  function next(event) {
    event.preventDefault();
    const message = validateStep();
    if (message) {
      setError(message);
      return;
    }
    setError("");
    setStep((current) => Math.min(current + 1, 5));
  }

  async function submit(event) {
    event.preventDefault();
    const message = validateStep();
    if (message && step !== 5) {
      setError(message);
      return;
    }
    setError("");
    setLoading(true);
    try {
      const response = await fetch("/api/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          email: values.email,
          password: values.password,
          alias: values.alias,
          display_name: values.display_name,
          birth_date: values.birth_date,
          gender: values.gender,
          interest_ids: interestIds,
        }),
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) {
        setError(body?.error?.message || "No se pudo completar el registro.");
        const field = body?.error?.details?.field;
        if (field === "display_name") setStep(1);
        else if (field === "email" || field === "alias") setStep(2);
        else if (field === "password") setStep(3);
        else if (field === "birth_date" || field === "gender") setStep(4);
        else if (field === "interest_ids") setStep(5);
        return;
      }
      router.push(`/verify-pending?email=${encodeURIComponent(values.email)}`);
    } catch {
      setError("No se pudo conectar con el servidor. Comprueba tu conexión.");
    } finally {
      setLoading(false);
    }
  }

  function toggleInterest(id) {
    setInterestIds((current) =>
      current.includes(id)
        ? current.filter((value) => value !== id)
        : current.length < 10
          ? [...current, id]
          : current,
    );
  }

  return (
    <>
      <div className="chatly-auth__progress" aria-label={`Paso ${step} de 5`}>
        {[1, 2, 3, 4, 5].map((number) => (
          <span
            className={number <= step ? "chatly-auth__progress on" : "chatly-auth__progress"}
            key={number}
          />
        ))}
      </div>
      {error && <div className="chatly-auth__alert">{error}</div>}
      <form className="chatly-auth__stack chatly-auth__stack--wide" noValidate onSubmit={step < 5 ? next : submit}>
        {step === 1 && (
          <label className="chatly-auth__stack chatly-auth__stack--tight">
            <span className="chatly-auth__label">¿Cómo te llamas?</span>
            <input
              autoComplete="name"
              className="chatly-auth__input"
              maxLength={60}
              onChange={(event) => change("display_name", event.target.value)}
              required
              value={values.display_name}
            />
          </label>
        )}
        {step === 2 && (
          <>
            <label className="chatly-auth__stack chatly-auth__stack--tight">
              <span className="chatly-auth__label">Correo electrónico</span>
              <input
                autoComplete="email"
                className="chatly-auth__input"
                onChange={(event) => change("email", event.target.value)}
                required
                type="email"
                value={values.email}
              />
            </label>
            <label className="chatly-auth__stack chatly-auth__stack--tight">
              <span className="chatly-auth__label">Alias</span>
              <input
                autoComplete="username"
                className="chatly-auth__input"
                maxLength={20}
                onChange={(event) => change("alias", event.target.value)}
                required
                value={values.alias}
              />
            </label>
          </>
        )}
        {step === 3 && (
          <>
            <label className="chatly-auth__stack chatly-auth__stack--tight">
              <span className="chatly-auth__label">Contraseña</span>
              <input
                autoComplete="new-password"
                className="chatly-auth__input"
                onChange={(event) => change("password", event.target.value)}
                required
                type="password"
                value={values.password}
              />
            </label>
            <label className="chatly-auth__stack chatly-auth__stack--tight">
              <span className="chatly-auth__label">Confirma la contraseña</span>
              <input
                autoComplete="new-password"
                className="chatly-auth__input"
                onChange={(event) => change("password_confirm", event.target.value)}
                required
                type="password"
                value={values.password_confirm}
              />
            </label>
          </>
        )}
        {step === 4 && (
          <>
            <label className="chatly-auth__stack chatly-auth__stack--tight">
              <span className="chatly-auth__label">Fecha de nacimiento</span>
              <input
                className="chatly-auth__input"
                onChange={(event) => change("birth_date", event.target.value)}
                required
                type="date"
                value={values.birth_date}
              />
            </label>
            <label className="chatly-auth__stack chatly-auth__stack--tight">
              <span className="chatly-auth__label">Género</span>
              <select
                className="chatly-auth__input"
                onChange={(event) => change("gender", event.target.value)}
                required
                value={values.gender}
              >
                <option value="">Elige una opción</option>
                <option value="femenino">Femenino</option>
                <option value="masculino">Masculino</option>
              </select>
            </label>
          </>
        )}
        {step === 5 && (
          <section className="chatly-register-interests">
            <div className="chatly-auth__label">Intereses (opcional) · {interestIds.length}/10</div>
            {!catalogLoaded ? (
              <p>Cargando intereses…</p>
            ) : (
              catalog.map((category) => (
                <fieldset className="chatly-register-category" key={category.id}>
                  <legend>{category.name}</legend>
                  {category.interests.map((interest) => (
                    <label className="chatly-register-interest" key={interest.id}>
                      <input
                        checked={interestIds.includes(interest.id)}
                        disabled={!interestIds.includes(interest.id) && interestIds.length >= 10}
                        onChange={() => toggleInterest(interest.id)}
                        type="checkbox"
                      />
                      {interest.name}
                    </label>
                  ))}
                </fieldset>
              ))
            )}
          </section>
        )}

        <div className="chatly-register-actions">
          {step > 1 && (
            <button
              className="chatly-auth__button chatly-auth__button--secondary"
              onClick={() => {
                setError("");
                setStep((current) => current - 1);
              }}
              type="button"
            >
              Atrás
            </button>
          )}
          <button className="chatly-auth__button" disabled={loading} type="submit">
            {loading ? "Creando cuenta…" : step === 5 ? "Crear cuenta" : "Siguiente"}
          </button>
        </div>
      </form>
      <Link className="chatly-auth__link" href="/login">
        ¿Ya tienes cuenta? Inicia sesión
      </Link>
    </>
  );
}
