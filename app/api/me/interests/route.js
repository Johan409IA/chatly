import { ApiError, apiErrorResponse } from "../../../../lib/server/api-error.js";
import { replaceOwnInterests } from "../../../../lib/server/profile.js";
import { requireActor } from "../../../../lib/server/supabase-auth.js";
import { interestsUpdateSchema, parseBody } from "../../../../lib/shared/validation.js";

export async function PUT(request) {
  try {
    const actor = await requireActor(request);
    let input;
    try {
      input = await request.json();
    } catch {
      throw new ApiError("validation_error", "Revisa los datos enviados.", 422);
    }
    const { interest_ids: interestIds } = parseBody(interestsUpdateSchema, input);
    const profile = await replaceOwnInterests(actor, interestIds);
    if (!profile) {
      throw new ApiError("not_found", "No encontramos el perfil de esta cuenta.", 404);
    }
    return Response.json(profile);
  } catch (error) {
    return apiErrorResponse(error);
  }
}
