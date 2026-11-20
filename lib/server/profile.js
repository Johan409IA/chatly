import { ApiError } from "./api-error.js";
import { withActorTransaction } from "./database.js";

function calculateAge(value) {
  const birthDate = new Date(`${value}T00:00:00Z`);
  const today = new Date();
  let age = today.getUTCFullYear() - birthDate.getUTCFullYear();
  if (
    today.getUTCMonth() < birthDate.getUTCMonth() ||
    (today.getUTCMonth() === birthDate.getUTCMonth() &&
      today.getUTCDate() < birthDate.getUTCDate())
  ) {
    age -= 1;
  }
  return age;
}

export async function getOwnProfile(actor) {
  return withActorTransaction(actor.id, async (client) => {
    const result = await client.query(
      `SELECT
         p.id::text AS id,
         p.alias,
         p.nombre_visible AS display_name,
         p.ruta_avatar AS avatar_url,
         p.fecha_nacimiento::text AS birth_date,
         p.genero AS gender,
         p.alias_cambiado_en AS alias_changed_at,
         p.visibilidad_publica AS is_public,
         p.creado_en AS created_at,
         (p.correo_verificado_en IS NOT NULL) AS email_verified,
         i.id::text AS interest_id,
         i.nombre AS interest_name,
         ci.nombre AS interest_category,
         ci.orden AS category_order
       FROM public.perfiles AS p
       LEFT JOIN public.intereses_usuario AS iu ON iu.usuario_id = p.id
       LEFT JOIN public.intereses AS i
         ON i.id = iu.interes_id AND i.activo = true
       LEFT JOIN public.categorias_interes AS ci
         ON ci.id = i.categoria_id AND ci.activa = true
       WHERE p.id = $1 AND p.eliminado_en IS NULL
       ORDER BY ci.orden, i.nombre`,
      [actor.id],
    );
    if (!result.rows.length) return null;

    const row = result.rows[0];
    const aliasChangedAt = row.alias_changed_at
      ? new Date(row.alias_changed_at)
      : null;
    const canChangeAlias =
      !aliasChangedAt || Date.now() - aliasChangedAt.getTime() >= 30 * 24 * 60 * 60 * 1000;
    const interests = result.rows
      .filter((interest) => interest.interest_id)
      .map((interest) => ({
        id: interest.interest_id,
        name: interest.interest_name,
        category: interest.interest_category,
      }));

    return {
      id: row.id,
      email: actor.email,
      email_verified: row.email_verified,
      alias: row.alias,
      display_name: row.display_name,
      avatar_url: row.avatar_url,
      birth_date: row.birth_date,
      age: calculateAge(row.birth_date),
      gender: row.gender,
      alias_changed_at: row.alias_changed_at,
      can_change_alias: canChangeAlias,
      is_public: row.is_public,
      interests,
      created_at: row.created_at,
    };
  });
}

export async function getLoginProfile(actorId) {
  return withActorTransaction(actorId, async (client) => {
    const result = await client.query(
      `SELECT alias, nombre_visible AS display_name,
              (correo_verificado_en IS NOT NULL) AS email_verified
       FROM public.perfiles
       WHERE id = $1 AND eliminado_en IS NULL`,
      [actorId],
    );
    return result.rows[0] || null;
  });
}

async function writeAudit(client, actorId, action, entityType, before, after) {
  const beforeValue = Object.keys(before).length ? JSON.stringify(before) : null;
  const afterValue = Object.keys(after).length ? JSON.stringify(after) : null;
  await client.query(
    `INSERT INTO public.registros_auditoria
       (actor_id, accion, tipo_entidad, entidad_id, valores_anteriores, valores_nuevos)
     VALUES (app.current_actor_id(), $1, $2, $3, $4::jsonb, $5::jsonb)`,
    [action, entityType, actorId, beforeValue, afterValue],
  );
}

export async function updateOwnProfile(actor, change) {
  const columnMap = {
    display_name: "nombre_visible",
    alias: "alias",
    birth_date: "fecha_nacimiento",
    gender: "genero",
    is_public: "visibilidad_publica",
  };
  const requested = Object.entries(columnMap).filter(([field]) => change[field] !== undefined && change[field] !== null);
  if (!requested.length) {
    throw new ApiError("validation_error", "Indica al menos un campo para actualizar.", 422);
  }

  const updated = await withActorTransaction(actor.id, async (client) => {
    const selected = await client.query(
      `SELECT alias, nombre_visible AS display_name,
              fecha_nacimiento::text AS birth_date, genero AS gender,
              visibilidad_publica AS is_public, alias_cambiado_en
       FROM public.perfiles
       WHERE id = $1 AND eliminado_en IS NULL
       FOR UPDATE`,
      [actor.id],
    );
    const current = selected.rows[0];
    if (!current) return false;

    const before = {};
    const after = {};
    const updates = [];
    for (const [field, column] of requested) {
      const value = change[field];
      const oldValue = current[field];
      if (value === oldValue) continue;
      if (field === "alias") {
        const changedAt = current.alias_cambiado_en
          ? new Date(current.alias_cambiado_en).getTime()
          : null;
        if (changedAt && Date.now() - changedAt < 30 * 24 * 60 * 60 * 1000) {
          throw new ApiError(
            "alias_change_too_soon",
            "Solo puedes cambiar tu alias una vez cada 30 días.",
            422,
          );
        }
        const exists = await client.query("SELECT app.alias_exists($1) AS exists", [value]);
        if (exists.rows[0]?.exists) {
          throw new ApiError("alias_taken", "Ese alias ya está en uso. Elige otro.", 409);
        }
      }
      before[column] = oldValue instanceof Date ? oldValue.toISOString() : oldValue;
      after[column] = value;
      updates.push([column, value]);
    }

    if (!updates.length) return true;
    const assignments = updates.map(([column], index) => `${column} = $${index + 2}`);
    if (updates.some(([column]) => column === "alias")) {
      assignments.push("alias_cambiado_en = now()");
    }
    assignments.push("actualizado_en = now()");
    await client.query(
      `UPDATE public.perfiles
       SET ${assignments.join(", ")}
       WHERE id = $1 AND eliminado_en IS NULL`,
      [actor.id, ...updates.map(([, value]) => value)],
    );
    await writeAudit(client, actor.id, "perfil_actualizado", "perfiles", before, after);
    return true;
  });
  return updated ? getOwnProfile(actor) : null;
}

export async function replaceOwnInterests(actor, interestIds) {
  await withActorTransaction(actor.id, async (client) => {
    const currentResult = await client.query(
      `SELECT interes_id::text AS id
       FROM public.intereses_usuario
       WHERE usuario_id = $1
       ORDER BY interes_id`,
      [actor.id],
    );
    const beforeIds = currentResult.rows.map((row) => row.id);
    const requestedIds = [...interestIds];
    const sameSet =
      beforeIds.length === requestedIds.length &&
      [...requestedIds].sort().every((id, index) => id === beforeIds[index]);

    await client.query(
      "DELETE FROM public.intereses_usuario WHERE usuario_id = $1",
      [actor.id],
    );
    if (requestedIds.length) {
      const inserted = await client.query(
        `INSERT INTO public.intereses_usuario (usuario_id, interes_id)
         SELECT $1, i.id
         FROM public.intereses AS i
         WHERE i.id = ANY($2::uuid[]) AND i.activo
         RETURNING interes_id`,
        [actor.id, requestedIds],
      );
      if (inserted.rowCount !== requestedIds.length) {
        throw new ApiError(
          "validation_error",
          "Uno o más intereses ya no están disponibles.",
          422,
        );
      }
    }
    if (!sameSet) {
      await writeAudit(
        client,
        actor.id,
        "intereses_usuario_reemplazados",
        "intereses_usuario",
        { interes_ids: [...beforeIds].sort() },
        { interes_ids: requestedIds },
      );
    }
  });
  return getOwnProfile(actor);
}
