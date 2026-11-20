import { ApiError, apiErrorResponse } from "../../../lib/server/api-error.js";
import { getOwnProfile, updateOwnProfile } from "../../../lib/server/profile.js";
import { requireActor } from "../../../lib/server/supabase-auth.js";
import { parseBody, profileUpdateSchema } from "../../../lib/shared/validation.js";

export async function GET(request) {
  try {
    const actor = await requireActor(request);
    const profile = await getOwnProfile(actor);
    if (!profile) {
      throw new ApiError("not_found", "No encontramos el perfil de esta cuenta.", 404);
    }
    return Response.json(profile);
  } catch (error) {
    return apiErrorResponse(error);
  }
}

export async function PATCH(request) {
  try {
    const actor = await requireActor(request);
    let input;
    try {
      input = await request.json();
    } catch {
      throw new ApiError("validation_error", "Revisa los datos enviados.", 422);
    }
    const changes = parseBody(profileUpdateSchema, input);
    const profile = await updateOwnProfile(actor, changes);
    if (!profile) {
      throw new ApiError("not_found", "No encontramos el perfil de esta cuenta.", 404);
    }
    return Response.json(profile);
  } catch (error) {
    return apiErrorResponse(error);
  }
}
