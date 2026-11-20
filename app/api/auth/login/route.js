import { NextResponse } from "next/server";
import { z } from "zod";
import { ApiError, apiErrorResponse } from "../../../../lib/server/api-error.js";
import { getLoginProfile } from "../../../../lib/server/profile.js";
import {
  mapSupabaseAuthError,
  setSessionCookies,
  supabaseAuthRequest,
  verifyAccessToken,
} from "../../../../lib/server/supabase-auth.js";
import { parseBody } from "../../../../lib/shared/validation.js";

const schema = z.object({
  email: z.string().trim().toLowerCase().email(),
  password: z.string().min(1),
});

export async function POST(request) {
  try {
    let input;
    try {
      input = await request.json();
    } catch {
      throw new ApiError("validation_error", "Revisa los datos enviados.", 422);
    }
    const body = parseBody(schema, input);
    const { data, response } = await supabaseAuthRequest("/token?grant_type=password", {
      body,
    });
    if (!response.ok) {
      throw mapSupabaseAuthError(data, response.status);
    }
    if (
      typeof data.access_token !== "string" ||
      typeof data.refresh_token !== "string" ||
      !data.user?.id
    ) {
      throw new ApiError("internal_error", "No se pudo iniciar la sesión.", 502);
    }

    const actor = await verifyAccessToken(data.access_token);
    if (actor.id !== data.user.id) {
      throw new ApiError("unauthorized", "La sesión recibida no es válida.", 401);
    }
    const profile = await getLoginProfile(actor.id);
    if (!profile) {
      throw new ApiError("not_found", "No encontramos el perfil de esta cuenta.", 404);
    }
    if (!profile.email_verified) {
      throw new ApiError(
        "email_not_verified",
        "Confirma tu correo para poder entrar.",
        403,
      );
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
  } catch (error) {
    return apiErrorResponse(error);
  }
}
