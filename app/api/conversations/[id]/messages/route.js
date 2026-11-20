import { NextResponse } from "next/server";
import { z } from "zod";
import { ApiError, apiErrorResponse } from "../../../../../lib/server/api-error.js";
import { withActorTransaction } from "../../../../../lib/server/database.js";
import { getLoginProfile } from "../../../../../lib/server/profile.js";
import { requireActor } from "../../../../../lib/server/supabase-auth.js";
import { parseBody } from "../../../../../lib/shared/validation.js";

const sendSchema = z.object({
  content: z.string().trim().min(1).max(4000),
  client_message_id: z.string().uuid(),
  reply_to_message_id: z.string().uuid().nullable().optional(),
});

function requireVerifiedProfile(profile) {
  if (!profile) {
    throw new ApiError("not_found", "No encontramos el perfil de esta cuenta.", 404);
  }
  if (!profile.email_verified) {
    throw new ApiError("email_not_verified", "Confirma tu correo para usar el chat.", 403);
  }
}

function mapMessage(row) {
  return {
    id: row.id,
    conversation_id: row.conversation_id,
    type: row.type,
    author: row.author_id
      ? {
          id: row.author_id,
          alias: row.author_alias,
          display_name: row.author_name,
          avatar_url: row.author_avatar,
        }
      : null,
    content: row.deleted ? null : row.content,
    edited_at: row.edited_at,
    deleted: row.deleted,
    reply_to: row.reply_id
      ? {
          id: row.reply_id,
          author_alias: row.reply_author_alias,
          preview: row.reply_deleted ? "Se eliminó un mensaje" : row.reply_content,
        }
      : null,
    reactions: [],
    created_at: row.created_at,
    ...(row.type === "system"
      ? { system_event: row.system_event, system_data: row.system_data }
      : {}),
  };
}

async function selectMessages(client, conversationId, rows) {
  if (!rows.length) return [];
  const ids = rows.map((row) => row.id);
  const result = await client.query(
    `SELECT
       m.id::text AS id,
       m.conversacion_id::text AS conversation_id,
       m.tipo AS type,
       m.autor_id::text AS author_id,
       author.alias AS author_alias,
       author.nombre_visible AS author_name,
       author.ruta_avatar AS author_avatar,
       m.contenido AS content,
       m.editado_en AS edited_at,
       (m.eliminado_en IS NOT NULL) AS deleted,
       m.evento_sistema AS system_event,
       m.datos_evento AS system_data,
       m.mensaje_respuesta_id::text AS reply_id,
       reply.contenido AS reply_content,
       reply_author.alias AS reply_author_alias,
       (reply.eliminado_en IS NOT NULL) AS reply_deleted,
       m.creado_en AS created_at
     FROM public.mensajes AS m
     LEFT JOIN public.perfiles AS author ON author.id = m.autor_id
     LEFT JOIN public.mensajes AS reply ON reply.id = m.mensaje_respuesta_id
     LEFT JOIN public.perfiles AS reply_author ON reply_author.id = reply.autor_id
     WHERE m.id = ANY($1::uuid[])
     ORDER BY m.creado_en, m.id`,
    [ids],
  );
  return result.rows.map(mapMessage);
}

export async function GET(request, context) {
  try {
    const { id } = await context.params;
    if (!z.string().uuid().safeParse(id).success) {
      throw new ApiError("validation_error", "El identificador de conversación no es válido.", 422);
    }
    const actor = await requireActor(request);
    requireVerifiedProfile(await getLoginProfile(actor.id));

    const url = new URL(request.url);
    const beforeCreatedAt = url.searchParams.get("before_created_at");
    const beforeId = url.searchParams.get("before_id");
    if (Boolean(beforeCreatedAt) !== Boolean(beforeId)) {
      throw new ApiError(
        "validation_error",
        "Envía juntos before_created_at y before_id.",
        422,
      );
    }
    if (beforeId && !z.string().uuid().safeParse(beforeId).success) {
      throw new ApiError("validation_error", "El cursor de mensajes no es válido.", 422);
    }
    const pageSize = beforeId ? 30 : Number(url.searchParams.get("limit") || 50);
    if (!Number.isInteger(pageSize) || pageSize < 1 || pageSize > 50) {
      throw new ApiError("validation_error", "El límite debe estar entre 1 y 50.", 422);
    }
    if (beforeCreatedAt && Number.isNaN(Date.parse(beforeCreatedAt))) {
      throw new ApiError("validation_error", "El cursor de mensajes no es válido.", 422);
    }

    const result = await withActorTransaction(actor.id, async (client) => {
      const membership = await client.query(
        `SELECT id
         FROM public.miembros_conversacion
         WHERE conversacion_id = $1 AND usuario_id = $2
         LIMIT 1`,
        [id, actor.id],
      );
      if (!membership.rowCount) {
        throw new ApiError("not_found", "No encontramos esta conversación.", 404);
      }

      const query = beforeId
        ? await client.query(
            `SELECT id::text AS id, creado_en AS created_at
             FROM public.mensajes
             WHERE conversacion_id = $1
               AND (creado_en, id) < ($2::timestamptz, $3::uuid)
             ORDER BY creado_en DESC, id DESC
             LIMIT $4`,
            [id, beforeCreatedAt, beforeId, pageSize],
          )
        : await client.query(
            `SELECT id::text AS id, creado_en AS created_at
             FROM public.mensajes
             WHERE conversacion_id = $1
             ORDER BY creado_en DESC, id DESC
             LIMIT $2`,
            [id, pageSize],
          );
      const messages = await selectMessages(client, id, query.rows);
      return { messages, nextCursor: query.rows.length === pageSize ? query.rows.at(-1) : null };
    });
    const ordered = result.messages.reverse();
    return NextResponse.json({
      items: ordered,
      next_cursor: result.nextCursor
        ? {
            created_at: result.nextCursor.created_at,
            id: result.nextCursor.id,
          }
        : null,
    });
  } catch (error) {
    return apiErrorResponse(error);
  }
}

export async function POST(request, context) {
  try {
    const { id } = await context.params;
    if (!z.string().uuid().safeParse(id).success) {
      throw new ApiError("validation_error", "El identificador de conversación no es válido.", 422);
    }
    const actor = await requireActor(request);
    requireVerifiedProfile(await getLoginProfile(actor.id));

    let input;
    try {
      input = await request.json();
    } catch {
      throw new ApiError("validation_error", "Revisa los datos enviados.", 422);
    }
    const body = parseBody(sendSchema, input);
    const result = await withActorTransaction(actor.id, async (client) => {
      const memberships = await client.query(
        `SELECT bool_or(salido_en IS NULL) AS active
         FROM public.miembros_conversacion
         WHERE conversacion_id = $1 AND usuario_id = $2`,
        [id, actor.id],
      );
      if (memberships.rows[0]?.active !== true) {
        const hasHistory = memberships.rows[0]?.active === false;
        throw new ApiError(
          hasHistory ? "read_only_period" : "not_member",
          hasHistory
            ? "Ya no puedes enviar mensajes en esta conversación."
            : "No eres integrante de esta conversación.",
          403,
        );
      }

      if (body.reply_to_message_id) {
        const reply = await client.query(
          `SELECT id FROM public.mensajes
           WHERE id = $1 AND conversacion_id = $2`,
          [body.reply_to_message_id, id],
        );
        if (!reply.rowCount) {
          throw new ApiError(
            "validation_error",
            "El mensaje al que respondes no pertenece a esta conversación.",
            422,
          );
        }
      }

      const existing = await client.query(
        `SELECT id::text AS id, conversacion_id::text AS conversation_id
         FROM public.mensajes
         WHERE autor_id = $1 AND id_mensaje_cliente = $2`,
        [actor.id, body.client_message_id],
      );
      if (existing.rowCount) {
        if (existing.rows[0].conversation_id !== id) {
          throw new ApiError(
            "validation_error",
            "El identificador del mensaje ya se usó en otra conversación.",
            422,
          );
        }
        return { id: existing.rows[0].id, replay: true };
      }

      const inserted = await client.query(
        `INSERT INTO public.mensajes
           (conversacion_id, autor_id, tipo, contenido,
            mensaje_respuesta_id, id_mensaje_cliente)
         VALUES ($1, $2, 'text', $3, $4, $5)
         ON CONFLICT (autor_id, id_mensaje_cliente)
           WHERE id_mensaje_cliente IS NOT NULL
           DO NOTHING
         RETURNING id::text AS id`,
        [id, actor.id, body.content, body.reply_to_message_id || null, body.client_message_id],
      );
      if (inserted.rowCount) return { id: inserted.rows[0].id, replay: false };

      const replay = await client.query(
        `SELECT id::text AS id, conversacion_id::text AS conversation_id
         FROM public.mensajes
         WHERE autor_id = $1 AND id_mensaje_cliente = $2`,
        [actor.id, body.client_message_id],
      );
      if (!replay.rowCount || replay.rows[0].conversation_id !== id) {
        throw new ApiError(
          "validation_error",
          "El identificador del mensaje ya se usó en otra conversación.",
          422,
        );
      }
      return { id: replay.rows[0].id, replay: true };
    });

    const message = await withActorTransaction(actor.id, async (client) => {
      const result = await client.query(
        `SELECT
           m.id::text AS id,
           m.conversacion_id::text AS conversation_id,
           m.tipo AS type,
           m.autor_id::text AS author_id,
           author.alias AS author_alias,
           author.nombre_visible AS author_name,
           author.ruta_avatar AS author_avatar,
           m.contenido AS content,
           m.editado_en AS edited_at,
           (m.eliminado_en IS NOT NULL) AS deleted,
           m.evento_sistema AS system_event,
           m.datos_evento AS system_data,
           m.mensaje_respuesta_id::text AS reply_id,
           reply.contenido AS reply_content,
           reply_author.alias AS reply_author_alias,
           (reply.eliminado_en IS NOT NULL) AS reply_deleted,
           m.creado_en AS created_at
         FROM public.mensajes AS m
         LEFT JOIN public.perfiles AS author ON author.id = m.autor_id
         LEFT JOIN public.mensajes AS reply ON reply.id = m.mensaje_respuesta_id
         LEFT JOIN public.perfiles AS reply_author ON reply_author.id = reply.autor_id
         WHERE m.id = $1`,
        [result.id],
      );
      return mapMessage(result.rows[0]);
    });
    return NextResponse.json(
      { message, idempotent_replay: result.replay },
      { status: result.replay ? 200 : 201 },
    );
  } catch (error) {
    return apiErrorResponse(error);
  }
}
