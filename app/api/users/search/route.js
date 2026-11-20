import { NextResponse } from "next/server";
import { ApiError, apiErrorResponse } from "../../../../lib/server/api-error.js";
import { withActorTransaction } from "../../../../lib/server/database.js";
import { getLoginProfile } from "../../../../lib/server/profile.js";
import { requireActor } from "../../../../lib/server/supabase-auth.js";

const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function mapResult(row) {
  return {
    id: String(row.id),
    alias: row.alias,
    display_name: row.display_name || row.nombre_visible,
    avatar_url: row.avatar_url || row.ruta_avatar || null,
  };
}

export async function GET(request) {
  try {
    const actor = await requireActor(request);
    const profile = await getLoginProfile(actor.id);
    if (!profile?.email_verified) {
      throw new ApiError("email_not_verified", "Confirma tu correo para usar esta búsqueda.", 403);
    }

    const parameters = new URL(request.url).searchParams;
    const aliasQuery = parameters.get("q");
    const emailQuery = parameters.get("email");
    if ((aliasQuery === null) === (emailQuery === null)) {
      throw new ApiError(
        "validation_error",
        "Indica un parámetro de búsqueda: q o email, pero no ambos.",
        422,
      );
    }

    const results = await withActorTransaction(actor.id, async (client) => {
      if (aliasQuery !== null) {
        const query = aliasQuery.trim();
        if (query.length < 2) {
          throw new ApiError("validation_error", "La búsqueda por alias necesita al menos 2 caracteres.", 422);
        }
        const escaped = query.replace(/[\\%_]/g, "\\$&");
        const response = await client.query(
          `SELECT id::text AS id, alias,
                  nombre_visible AS display_name, ruta_avatar AS avatar_url
           FROM public.perfiles
           WHERE eliminado_en IS NULL AND id <> $1
             AND alias ILIKE $2 ESCAPE '\\'
           ORDER BY alias
           LIMIT 20`,
          [actor.id, `%${escaped}%`],
        );
        return response.rows;
      }

      const email = emailQuery.trim().toLowerCase();
      if (!emailPattern.test(email)) {
        throw new ApiError("validation_error", "Escribe un correo válido.", 422);
      }
      const response = await client.query(
        "SELECT * FROM app.buscar_usuario_por_correo($1)",
        [email],
      );
      return response.rows;
    });
    return NextResponse.json({ results: results.map(mapResult) });
  } catch (error) {
    return apiErrorResponse(error);
  }
}
