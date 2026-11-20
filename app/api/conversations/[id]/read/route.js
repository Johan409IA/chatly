import { z } from "zod";
import { ApiError, apiErrorResponse } from "../../../../../lib/server/api-error.js";
import { withActorTransaction } from "../../../../../lib/server/database.js";
import { getLoginProfile } from "../../../../../lib/server/profile.js";
import { requireActor } from "../../../../../lib/server/supabase-auth.js";

const bodySchema = z.object({ message_id: z.string().uuid() });

export async function POST(request, context) {
  try {
    const { id } = await context.params;
    if (!z.string().uuid().safeParse(id).success) {
      throw new ApiError("validation_error", "El identificador de conversación no es válido.", 422);
    }
    const actor = await requireActor(request);
    const profile = await getLoginProfile(actor.id);
    if (!profile?.email_verified) {
      throw new ApiError("email_not_verified", "Confirma tu correo para usar el chat.", 403);
    }

    let input;
    try {
      input = await request.json();
    } catch {
      throw new ApiError("validation_error", "Revisa los datos enviados.", 422);
    }
    const parsed = bodySchema.safeParse(input);
    if (!parsed.success) {
      throw new ApiError("validation_error", "Indica el mensaje que quieres marcar como leído.", 422);
    }

    const result = await withActorTransaction(actor.id, async (client) => {
      const membership = await client.query(
        `SELECT id
         FROM public.miembros_conversacion
         WHERE conversacion_id = $1 AND usuario_id = $2 AND salido_en IS NULL
         FOR UPDATE`,
        [id, actor.id],
      );
      if (!membership.rowCount) {
        throw new ApiError("not_member", "No eres integrante activo de esta conversación.", 403);
      }
      const message = await client.query(
        `SELECT id::text AS id, creado_en
         FROM public.mensajes
         WHERE id = $1 AND conversacion_id = $2`,
        [parsed.data.message_id, id],
      );
      if (!message.rowCount) {
        throw new ApiError("not_found", "No encontramos ese mensaje.", 404);
      }
      const updated = await client.query(
        `UPDATE public.miembros_conversacion
         SET ultimo_mensaje_leido_id = $3,
             ultimo_leido_en = $4,
             actualizado_en = now()
         WHERE conversacion_id = $1
           AND usuario_id = $2
           AND salido_en IS NULL
           AND (ultimo_leido_en IS NULL OR ultimo_leido_en <= $4)
         RETURNING ultimo_mensaje_leido_id::text AS last_read_message_id,
                   ultimo_leido_en AS last_read_at`,
        [id, actor.id, parsed.data.message_id, message.rows[0].creado_en],
      );
      if (updated.rowCount) {
        return {
          last_read_message_id: updated.rows[0].last_read_message_id,
          last_read_at: updated.rows[0].last_read_at,
        };
      }
      const current = await client.query(
        `SELECT ultimo_mensaje_leido_id::text AS last_read_message_id,
                ultimo_leido_en AS last_read_at
         FROM public.miembros_conversacion
         WHERE conversacion_id = $1 AND usuario_id = $2 AND salido_en IS NULL`,
        [id, actor.id],
      );
      return {
        last_read_message_id: current.rows[0].last_read_message_id,
        last_read_at: current.rows[0].last_read_at,
      };
    });
    return Response.json(result);
  } catch (error) {
    return apiErrorResponse(error);
  }
}
