"""Lecturas de mensajes (§7.10, Q60/Q101): el integrante marca su propio read.

La infraestructura ya existía (`miembros_conversacion.ultimo_mensaje_leido_id`
y `ultimo_leido_en`, con el índice `ix_miembros_ultimo_leido` de 0003) y
`unread_count` ya deriva de `ultimo_leido_en`, pero el trigger
`proteger_periodo_membresia` de `0007_rls` solo dejaba al propio usuario
modificar su fila para salir de la conversación (`estado = 'left'`): cualquier
UPDATE de lectura era rechazado con 42501.

Esta migración añade una vía al trigger: el integrante activo puede actualizar
su propia fila cuando las únicas columnas que cambian son las de lectura
(`ultimo_mensaje_leido_id`, `ultimo_leido_en` y el marcador `actualizado_en`).
Todo lo demás sigue bloqueado; el admin conserva su vía completa.

Fuente: `docs/api-contracts.md` §7.10 y `docs/chatly.md` Q60/Q101.
"""

from alembic import op

revision = "0015_lecturas_membresia"
down_revision = "0014_rls_chat_directo"
branch_labels = None
depends_on = None

_TRIGGER_ACTUAL = """
create or replace function public.proteger_periodo_membresia()
returns trigger
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
    v_actor uuid := (select app.current_actor_id());
begin
    if new.conversacion_id <> old.conversacion_id
       or new.usuario_id <> old.usuario_id
       or new.unido_en <> old.unido_en then
            raise exception 'No se puede cambiar la conversación, el usuario'
                ' ni el inicio del periodo.'
                using errcode = '42501';
    end if;

    if old.salido_en is not null then
        raise exception 'Un periodo de membresía cerrado no se reabre.'
            using errcode = '42501';
    end if;

    -- Sin contexto de actor no hay política RLS que permita el UPDATE;
    -- se deja pasar para migraciones y semillas.
    if v_actor is null then
        return new;
    end if;

    if (select app.is_active_admin(old.conversacion_id)) then
        return new;
    end if;

    if old.usuario_id = v_actor
       and new.estado = 'left'
       and new.salido_en is not null
       and new.retirado_por is null
       and new.rol = old.rol then
        return new;
    end if;

    raise exception 'No tienes permiso para modificar esta membresía.'
        using errcode = '42501';
end $$;
"""

_TRIGGER_LECTURAS = """
create or replace function public.proteger_periodo_membresia()
returns trigger
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
    v_actor uuid := (select app.current_actor_id());
begin
    if new.conversacion_id <> old.conversacion_id
       or new.usuario_id <> old.usuario_id
       or new.unido_en <> old.unido_en then
            raise exception 'No se puede cambiar la conversación, el usuario'
                ' ni el inicio del periodo.'
                using errcode = '42501';
    end if;

    if old.salido_en is not null then
        raise exception 'Un periodo de membresía cerrado no se reabre.'
            using errcode = '42501';
    end if;

    -- Sin contexto de actor no hay política RLS que permita el UPDATE;
    -- se deja pasar para migraciones y semillas.
    if v_actor is null then
        return new;
    end if;

    if (select app.is_active_admin(old.conversacion_id)) then
        return new;
    end if;

    -- §7.10: el propio integrante marca sus lecturas. La política
    -- `miembros_update_backend` ya lo autoriza; aquí se acota a que las
    -- únicas columnas que cambien sean las de lectura.
    if old.usuario_id = v_actor
       and new.rol = old.rol
       and new.estado = old.estado
       and new.salido_en is not distinct from old.salido_en
       and new.retirado_por is not distinct from old.retirado_por
       and new.agregado_por is not distinct from old.agregado_por then
        return new;
    end if;

    if old.usuario_id = v_actor
       and new.estado = 'left'
       and new.salido_en is not null
       and new.retirado_por is null
       and new.rol = old.rol then
        return new;
    end if;

    raise exception 'No tienes permiso para modificar esta membresía.'
        using errcode = '42501';
end $$;
"""


def upgrade() -> None:
    op.execute(_TRIGGER_LECTURAS)


def downgrade() -> None:
    op.execute(_TRIGGER_ACTUAL)
