import { createRemoteJWKSet, jwtVerify } from "jose";
import { getServerEnvironment } from "./environment.js";
import { ApiError } from "./api-error.js";

const ACCESS_COOKIE = "chatly_at";
const REFRESH_COOKIE = "chatly_rt";
let jwks;

export function getAuthCookies(request) {
  const accessToken =
    request.headers.get("authorization")?.match(/^Bearer\s+(.+)$/i)?.[1]?.trim() ||
    request.cookies.get(ACCESS_COOKIE)?.value;
  const refreshToken = request.cookies.get(REFRESH_COOKIE)?.value;
  return { accessToken, refreshToken };
}

export async function verifyAccessToken(token) {
  const environment = getServerEnvironment();
  jwks ||= createRemoteJWKSet(new URL(environment.supabaseJwksUrl));
  try {
    const { payload } = await jwtVerify(token, jwks, {
      issuer: `${environment.supabaseUrl}/auth/v1`,
      audience: "authenticated",
      clockTolerance: environment.jwtLeewaySeconds,
    });
    if (typeof payload.sub !== "string" || !/^[0-9a-f-]{36}$/i.test(payload.sub)) {
      throw new Error("JWT subject is invalid.");
    }
    return { id: payload.sub, email: typeof payload.email === "string" ? payload.email : "" };
  } catch {
    throw new ApiError(
      "unauthorized",
      "Tu sesión no es válida o ha expirado. Inicia sesión de nuevo.",
      401,
    );
  }
}

export async function requireActor(request) {
  const { accessToken } = getAuthCookies(request);
  if (!accessToken) {
    throw new ApiError("unauthorized", "Inicia sesión para continuar.", 401);
  }
  return verifyAccessToken(accessToken);
}

export async function supabaseAuthRequest(path, { method = "POST", body, accessToken } = {}) {
  const environment = getServerEnvironment();
  let response;
  try {
    response = await fetch(`${environment.supabaseUrl}/auth/v1${path}`, {
      method,
      cache: "no-store",
      headers: {
        apikey: environment.supabasePublishableKey,
        Authorization: `Bearer ${accessToken || environment.supabasePublishableKey}`,
        "Content-Type": "application/json",
      },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
  } catch {
    throw new ApiError(
      "service_unavailable",
      "El servicio de cuentas no está disponible. Inténtalo de nuevo.",
      503,
    );
  }

  let data = {};
  try {
    data = await response.json();
  } catch {
    if (response.ok) {
      throw new ApiError("internal_error", "El servicio de cuentas respondió con datos no válidos.", 502);
    }
  }
  return { data, response };
}

export function mapSupabaseAuthError(data, status) {
  const code = String(data?.code || data?.error_code || data?.error || "");
  const mapped = {
    user_already_exists: ["email_already_registered", "Este correo ya está registrado.", 409],
    email_exists: ["email_already_registered", "Este correo ya está registrado.", 409],
    invalid_credentials: ["invalid_credentials", "Correo o contraseña incorrectos.", 401],
    email_not_confirmed: ["email_not_verified", "Confirma tu correo para poder entrar.", 403],
    weak_password: ["weak_password", "La contraseña no cumple las reglas.", 422],
    same_password: ["weak_password", "La contraseña debe ser diferente a la actual.", 422],
    over_email_send_rate_limit: [
      "rate_limited",
      "Demasiados intentos. Espera unos minutos.",
      429,
    ],
    refresh_token_not_found: ["unauthorized", "Tu sesión ya no es válida.", 401],
  }[code];
  if (mapped) return new ApiError(...mapped);
  if (status === 429) {
    return new ApiError("rate_limited", "Demasiados intentos. Espera unos minutos.", 429);
  }
  if (status === 401) {
    return new ApiError("unauthorized", "No se pudo validar la sesión.", 401);
  }
  if (status === 403) {
    return new ApiError("forbidden", "No tienes permiso para esta acción.", 403);
  }
  if (status >= 500) {
    return new ApiError(
      "internal_error",
      "El servicio de cuentas no está disponible. Inténtalo de nuevo.",
      503,
    );
  }
  return new ApiError("validation_error", "Revisa los datos enviados.", status || 422);
}

export function setSessionCookies(response, tokens) {
  const environment = getServerEnvironment();
  const secure = environment.appEnvironment === "production";
  response.cookies.set(ACCESS_COOKIE, tokens.access_token, {
    httpOnly: true,
    secure,
    sameSite: "lax",
    path: "/",
    maxAge: Number(tokens.expires_in || 3600),
  });
  response.cookies.set(REFRESH_COOKIE, tokens.refresh_token, {
    httpOnly: true,
    secure,
    sameSite: "lax",
    path: "/",
    maxAge: 30 * 24 * 60 * 60,
  });
}

export function clearSessionCookies(response) {
  const environment = getServerEnvironment();
  for (const name of [ACCESS_COOKIE, REFRESH_COOKIE]) {
    response.cookies.set(name, "", {
      httpOnly: true,
      secure: environment.appEnvironment === "production",
      sameSite: "lax",
      path: "/",
      maxAge: 0,
    });
  }
}
