import { NextResponse } from "next/server";
import { z } from "zod";
import { ApiError, apiErrorResponse } from "../../../../lib/server/api-error.js";
import { getPool, withActorTransaction } from "../../../../lib/server/database.js";
import { getServerEnvironment } from "../../../../lib/server/environment.js";
import { getLoginProfile } from "../../../../lib/server/profile.js";
import {
  clearSessionCookies,
  getAuthCookies,
  mapSupabaseAuthError,
  setSessionCookies,
  supabaseAuthRequest,
  verifyAccessToken,
} from "../../../../lib/server/supabase-auth.js";
import { parseBody, registrationSchema } from "../../../../lib/shared/validation.js";

const emailSchema = z.object({
  email: z.string().trim().toLowerCase().email(),
});
const resetSchema = z.object({
  token_hash: z.string().trim().min(1),
  password: registrationSchema.shape.password,
});
const confirmSchema = z
  .object({
    token_hash: z.string().trim().min(1).optional(),
    code: z.string().trim().min(1).optional(),
    type: z
      .enum(["signup", "invite", "magiclink", "recovery", "email_change"])
      .default("signup"),
  })
  .refine((value) => Boolean(value.token_hash || value.code), {
    message: "El enlace de confirmación no contiene un código válido.",
  });

function noContent() {
  return new NextResponse(null, { status: 204 });
}

async function validateSignupAvailability(alias, interestIds) {
  const client = await getPool().connect();
  try {
    const aliasResult = await client.query("SELECT app.alias_exists($1) AS exists", [alias]);
    if (aliasResult.rows[0]?.exists) {
      throw new ApiError("alias_taken", "Ese alias ya está en uso. Elige otro.", 409);
    }

    if (interestIds.length) {
      const catalog = await client.query("SELECT * FROM app.catalogo_intereses()");
      const availableIds = new Set(
        catalog.rows.map((row) => String(row.interes_id || row.id || "")),
      );
      if (interestIds.some((id) => !availableIds.has(id))) {
        throw new ApiError("validation_error", "La selección de intereses no es válida.", 422);
      }
    }
  } finally {
    client.release();
  }
}

async function createSignupProfile(userId, body) {
  await withActorTransaction(userId, async (client) => {
    await client.query(
      `INSERT INTO public.perfiles
         (id, alias, nombre_visible, fecha_nacimiento, genero)
       VALUES ($1, $2, $3, $4::date, $5)`,
      [userId, body.alias, body.display_name, body.birth_date, body.gender],
    );
    await client.query(
      `INSERT INTO public.contactos_usuario (usuario_id, correo_normalizado)
       VALUES ($1, $2)`,
      [userId, body.email],
    );
    if (body.interest_ids.length) {
      const inserted = await client.query(
        `INSERT INTO public.intereses_usuario (usuario_id, interes_id)
         SELECT $1, i.id
         FROM public.intereses AS i
         WHERE i.id = ANY($2::uuid[]) AND i.activo
         RETURNING interes_id`,
        [userId, body.interest_ids],
      );
      if (inserted.rowCount !== body.interest_ids.length) {
        throw new ApiError("validation_error", "La selección de intereses cambió. Inténtalo otra vez.", 422);
      }
    }
  });
}

async function register(request) {
  let input;
  try {
    input = await request.json();
  } catch {
    throw new ApiError("validation_error", "Revisa los datos enviados.", 422);
  }
  const body = parseBody(registrationSchema, input);
  await validateSignupAvailability(body.alias, body.interest_ids);

  const environment = getServerEnvironment();
  const { data, response } = await supabaseAuthRequest(
    `/signup?redirect_to=${encodeURIComponent(`${environment.frontendUrl}/auth/confirm`)}`,
    {
      body: {
        email: body.email,
        password: body.password,
        data: {
          alias: body.alias,
          nombre_visible: body.display_name,
          fecha_nacimiento: body.birth_date,
          genero: body.gender,
        },
      },
    },
  );
  if (!response.ok) throw mapSupabaseAuthError(data, response.status);
  if (typeof data.user?.id !== "string") {
    throw new ApiError("internal_error", "No se pudo completar el registro.", 502);
  }
  await createSignupProfile(data.user.id, body);
  return NextResponse.json(
    {
      user_id: data.user.id,
      status: "verification_required",
      email: body.email,
    },
    { status: 201 },
  );
}

async function refresh(request) {
  const { refreshToken } = getAuthCookies(request);
  if (!refreshToken) {
    throw new ApiError("unauthorized", "Tu sesión ya no es válida. Inicia sesión de nuevo.", 401);
  }
  const { data, response } = await supabaseAuthRequest("/token?grant_type=refresh_token", {
    body: { refresh_token: refreshToken },
  });
  if (!response.ok) throw mapSupabaseAuthError(data, response.status);
  if (typeof data.access_token !== "string" || typeof data.refresh_token !== "string") {
    throw new ApiError("internal_error", "No se pudo renovar la sesión.", 502);
  }
  const actor = await verifyAccessToken(data.access_token);
  const profile = await getLoginProfile(actor.id);
  if (!profile) {
    throw new ApiError("not_found", "No encontramos el perfil de esta cuenta.", 404);
  }
  if (!profile.email_verified) {
    throw new ApiError("email_not_verified", "Confirma tu correo para poder entrar.", 403);
  }

  const result = NextResponse.json({
    access_token: data.access_token,
    expires_in: data.expires_in,
    user: {
      id: actor.id,
      alias: profile.alias,
      display_name: profile.display_name,
      email_verified: profile.email_verified,
    },
  });
  setSessionCookies(result, data);
  return result;
}

async function logout(request) {
  const { accessToken } = getAuthCookies(request);
  if (accessToken) {
    const { response } = await supabaseAuthRequest("/logout", { accessToken });
    if (!response.ok && response.status !== 401) {
      throw new ApiError("internal_error", "No se pudo cerrar la sesión.", 503);
    }
  }
  const result = noContent();
  clearSessionCookies(result);
  return result;
}

async function sendNeutralEmail(request, path) {
  let input;
  try {
    input = await request.json();
  } catch {
    throw new ApiError("validation_error", "Revisa los datos enviados.", 422);
  }
  const { email } = parseBody(emailSchema, input);
  try {
    await supabaseAuthRequest(path, { body: { email } });
  } catch {
    // Supabase's response must not disclose whether the address is registered.
  }
  return NextResponse.json({ status: "sent" }, { status: 202 });
}

async function resetPassword(request) {
  let input;
  try {
    input = await request.json();
  } catch {
    throw new ApiError("validation_error", "Revisa los datos enviados.", 422);
  }
  const body = parseBody(resetSchema, input);
  const verified = await supabaseAuthRequest("/verify", {
    body: { token_hash: body.token_hash, type: "recovery" },
  });
  if (!verified.response.ok) {
    throw mapSupabaseAuthError(verified.data, verified.response.status);
  }
  if (typeof verified.data.access_token !== "string") {
    throw new ApiError("unauthorized", "El enlace no es válido o ha caducado.", 401);
  }
  const changed = await supabaseAuthRequest("/user", {
    method: "PUT",
    accessToken: verified.data.access_token,
    body: { password: body.password },
  });
  if (!changed.response.ok) throw mapSupabaseAuthError(changed.data, changed.response.status);
  return noContent();
}

async function confirmEmail(request) {
  let input;
  try {
    input = await request.json();
  } catch {
    throw new ApiError("validation_error", "Revisa los datos enviados.", 422);
  }
  const body = parseBody(confirmSchema, input);
  const result = body.token_hash
    ? await supabaseAuthRequest("/verify", {
        body: { token_hash: body.token_hash, type: body.type },
      })
    : await supabaseAuthRequest("/token?grant_type=pkce", {
        body: { auth_code: body.code },
      });
  if (!result.response.ok) {
    throw mapSupabaseAuthError(result.data, result.response.status);
  }
  return noContent();
}

export async function POST(request, context) {
  try {
    const { action } = await context.params;
    switch (action) {
      case "register":
        return await register(request);
      case "refresh":
        return await refresh(request);
      case "logout":
        return await logout(request);
      case "resend-verification":
        return await sendNeutralEmail(request, "/resend");
      case "forgot-password":
        return await sendNeutralEmail(request, "/recover");
      case "reset-password":
        return await resetPassword(request);
      case "confirm":
        return await confirmEmail(request);
      default:
        throw new ApiError("not_found", "No encontramos esta ruta.", 404);
    }
  } catch (error) {
    return apiErrorResponse(error);
  }
}
