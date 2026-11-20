import { NextResponse } from "next/server";
import { ApiError, apiErrorResponse } from "../../../lib/server/api-error.js";
import { withActorTransaction } from "../../../lib/server/database.js";
import { getLoginProfile } from "../../../lib/server/profile.js";
import { requireActor } from "../../../lib/server/supabase-auth.js";

function initials(name) {
  return (
    String(name || "")
      .trim()
      .split(/\s+/)
      .slice(0, 2)
      .map((part) => part[0] || "")
      .join("")
      .toUpperCase() || "CH"
  );
}

export async function GET(request) {
  try {
    const actor = await requireActor(request);
    const profile = await getLoginProfile(actor.id);
    if (!profile?.email_verified) {
      throw new ApiError(
        "email_not_verified",
        "Confirma tu correo para usar el chat.",
        403,
      );
    }

    const includeHidden = new URL(request.url).searchParams.get("include_hidden") === "true";
    const items = await withActorTransaction(actor.id, async (client) => {
      const result = await client.query(
        `SELECT
           c.id::text AS id,
           c.tipo AS type,
           COALESCE(c.nombre, peer.nombre_visible, peer.alias, 'Conversación') AS name,
           peer.ruta_avatar AS avatar_url,
           c.ultimo_mensaje_en AS last_message_at,
           c.archivada AS is_archived,
           mem.rol AS my_role,
           (SELECT count(*)
            FROM public.miembros_conversacion AS member_count
            WHERE member_count.conversacion_id = c.id
              AND member_count.salido_en IS NULL) AS members_count,
           COALESCE(unread.unread_count, 0)::int AS unread_count,
           CASE
             WHEN latest.id IS NULL THEN NULL
             WHEN latest.eliminado_en IS NOT NULL THEN 'Se eliminó un mensaje'
             WHEN c.tipo = 'group' AND author.alias IS NOT NULL
               THEN author.alias || ': ' || COALESCE(latest.contenido, '')
             ELSE COALESCE(latest.contenido, '')
           END AS last_message_preview
         FROM public.conversaciones AS c
         JOIN public.miembros_conversacion AS mem
           ON mem.conversacion_id = c.id
          AND mem.usuario_id = $1
          AND mem.salido_en IS NULL
         LEFT JOIN public.preferencias_conversacion AS pref
           ON pref.conversacion_id = c.id AND pref.usuario_id = $1
         LEFT JOIN LATERAL (
           SELECT p.nombre_visible, p.alias, p.ruta_avatar
           FROM public.miembros_conversacion AS peer_member
           JOIN public.perfiles AS p ON p.id = peer_member.usuario_id
           WHERE peer_member.conversacion_id = c.id
             AND peer_member.usuario_id <> $1
             AND peer_member.salido_en IS NULL
             AND p.eliminado_en IS NULL
           ORDER BY peer_member.unido_en
           LIMIT 1
         ) AS peer ON true
         LEFT JOIN LATERAL (
           SELECT m.id, m.contenido, m.autor_id, m.eliminado_en
           FROM public.mensajes AS m
           WHERE m.conversacion_id = c.id
           ORDER BY m.creado_en DESC, m.id DESC
           LIMIT 1
         ) AS latest ON true
         LEFT JOIN public.perfiles AS author ON author.id = latest.autor_id
         LEFT JOIN LATERAL (
           SELECT count(*)::int AS unread_count
           FROM public.mensajes AS m
           WHERE m.conversacion_id = c.id
             AND m.eliminado_en IS NULL
             AND m.autor_id IS DISTINCT FROM $1
             AND m.creado_en > COALESCE(mem.ultimo_leido_en, mem.unido_en)
         ) AS unread ON true
         WHERE c.eliminado_en IS NULL
           AND ($2::boolean OR COALESCE(pref.oculta, false) = false)
         ORDER BY c.ultimo_mensaje_en DESC NULLS LAST, c.id`,
        [actor.id, includeHidden],
      );
      return result.rows;
    });

    const mappedItems = items.map((item) => ({
      id: item.id,
      type: item.type,
      name: item.name,
      avatar_url: item.avatar_url,
      initials: initials(item.name),
      last_message_at: item.last_message_at,
      last_message_preview: item.last_message_preview,
      unread_count: Number(item.unread_count),
      is_archived: item.is_archived,
      my_role: item.my_role,
      members_count: Number(item.members_count),
    }));
    return NextResponse.json({
      items: mappedItems,
      total_unread: mappedItems.reduce((total, item) => total + item.unread_count, 0),
    });
  } catch (error) {
    return apiErrorResponse(error);
  }
}
