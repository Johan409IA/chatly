"""mensajes, versiones y reacciones

Revision ID: 0004_mensajes
Revises: 0003_conversaciones
Create Date: 2026-11-08

Crea los mensajes persistidos, sus versiones de edición y las reacciones.
Incluye la FK de `miembros_conversacion.ultimo_mensaje_leido_id` y el trigger
que actualiza `conversaciones.ultimo_mensaje_en`. Las políticas RLS se
incorporan en `0007_rls`.
"""

from alembic import op

revision = "0004_mensajes"
down_revision = "0003_conversaciones"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        create table if not exists public.mensajes (
            id                   uuid primary key default gen_random_uuid(),
            conversacion_id      uuid        not null
                                 references public.conversaciones (id) on delete cascade,
            autor_id             uuid        references public.perfiles (id),
            tipo                 text        not null default 'text',
            contenido            text,
            evento_sistema       text,
            datos_evento         jsonb,
            mensaje_respuesta_id uuid,
            id_mensaje_cliente   uuid,
            editado_en           timestamptz,
            conteo_ediciones     integer     not null default 0,
            eliminado_en         timestamptz,
            eliminado_por        uuid        references public.perfiles (id),
            creado_en            timestamptz not null default now(),
            actualizado_en       timestamptz not null default now(),

            constraint ck_mensajes_tipo check (tipo in ('text','system','poll')),
            constraint ck_mensajes_contenido check (
                (tipo = 'text'
                    and autor_id is not null
                    and contenido is not null
                    and char_length(btrim(contenido)) between 1 and 4000
                    and evento_sistema is null)
                or (tipo = 'system'
                    and autor_id is null
                    and contenido is null
                    and evento_sistema is not null)
                or (tipo = 'poll'
                    and autor_id is not null
                    and contenido is null
                    and evento_sistema is null)
            ),
            constraint ck_mensajes_evento_sistema check (
                evento_sistema is null
                or evento_sistema in ('conversation_created','member_added','member_removed',
                                      'member_left','admin_changed','name_changed')
            ),
            constraint ck_mensajes_ediciones check (conteo_ediciones >= 0),
            constraint ck_mensajes_sin_auto_respuesta check (
                mensaje_respuesta_id is null or mensaje_respuesta_id <> id
            ),
            constraint uq_mensajes_conversacion_id unique (conversacion_id, id)
        )
        """
    )

    op.execute(
        "create unique index if not exists uq_mensajes_id_cliente"
        " on public.mensajes (autor_id, id_mensaje_cliente)"
        " where id_mensaje_cliente is not null"
    )
    op.execute(
        "create index if not exists ix_mensajes_conversacion_cursor"
        " on public.mensajes (conversacion_id, creado_en desc, id desc)"
    )
    op.execute(
        "create index if not exists ix_mensajes_visibles"
        " on public.mensajes (conversacion_id, creado_en desc, id desc)"
        " where eliminado_en is null"
    )
    op.execute(
        "create index if not exists ix_mensajes_respuesta"
        " on public.mensajes (mensaje_respuesta_id)"
        " where mensaje_respuesta_id is not null"
    )
    op.execute(
        "create index if not exists ix_mensajes_autor on public.mensajes (autor_id, creado_en desc)"
    )

    # La respuesta debe pertenecer a la misma conversación.
    op.execute(
        """
        do $$
        begin
          if not exists (
            select 1 from pg_constraint
            where conname = 'fk_mensajes_respuesta'
              and conrelid = 'public.mensajes'::regclass
          ) then
            alter table public.mensajes
              add constraint fk_mensajes_respuesta
              foreign key (conversacion_id, mensaje_respuesta_id)
              references public.mensajes (conversacion_id, id);
          end if;
        end
        $$;
        """
    )

    op.execute(
        """
        create table if not exists public.versiones_mensaje (
            id          uuid primary key default gen_random_uuid(),
            mensaje_id  uuid        not null
                        references public.mensajes (id) on delete cascade,
            contenido   text        not null,
            editado_por uuid        not null references public.perfiles (id),
            creado_en   timestamptz not null default now(),

            constraint ck_versiones_mensaje_contenido
                check (char_length(btrim(contenido)) between 1 and 4000)
        )
        """
    )
    op.execute(
        "create index if not exists ix_versiones_mensaje_mensaje"
        " on public.versiones_mensaje (mensaje_id, creado_en desc)"
    )

    op.execute(
        """
        create table if not exists public.reacciones_mensaje (
            id             uuid primary key default gen_random_uuid(),
            mensaje_id     uuid        not null
                           references public.mensajes (id) on delete cascade,
            usuario_id     uuid        not null references public.perfiles (id),
            emoji          text        not null,
            eliminado_en   timestamptz,
            creado_en      timestamptz not null default now(),
            actualizado_en timestamptz not null default now(),

            constraint ck_reacciones_emoji
                check (emoji in ('👍','❤️','😂','😮','😢','🙏','✅'))
        )
        """
    )
    op.execute(
        "create unique index if not exists uq_reacciones_activas"
        " on public.reacciones_mensaje (mensaje_id, usuario_id)"
        " where eliminado_en is null"
    )
    op.execute(
        "create index if not exists ix_reacciones_mensaje"
        " on public.reacciones_mensaje (mensaje_id)"
        " where eliminado_en is null"
    )

    # FK que no podía declararse en 0003 porque `mensajes` aún no existía.
    op.execute(
        """
        do $$
        begin
          if not exists (
            select 1 from pg_constraint
            where conname = 'fk_miembros_ultimo_leido'
              and conrelid = 'public.miembros_conversacion'::regclass
          ) then
            alter table public.miembros_conversacion
              add constraint fk_miembros_ultimo_leido
              foreign key (ultimo_mensaje_leido_id) references public.mensajes (id);
          end if;
        end
        $$;
        """
    )

    op.execute(
        """
        create or replace function public.tocar_actividad_conversacion()
        returns trigger language plpgsql as $$
        begin
            update public.conversaciones
               set ultimo_mensaje_en =
                       greatest(coalesce(ultimo_mensaje_en, new.creado_en), new.creado_en),
                   actualizado_en = now()
             where id = new.conversacion_id;
            return new;
        end $$;
        """
    )
    op.execute("drop trigger if exists trg_mensajes_tocar_actividad on public.mensajes")
    op.execute(
        """
        create trigger trg_mensajes_tocar_actividad
            after insert on public.mensajes
            for each row execute function public.tocar_actividad_conversacion()
        """
    )

    for table in ("mensajes", "reacciones_mensaje"):
        op.execute(f"drop trigger if exists trg_{table}_actualizado on public.{table}")
        op.execute(
            f"""
            create trigger trg_{table}_actualizado
                before update on public.{table}
                for each row execute function public.tocar_actualizado_en()
            """
        )


def downgrade() -> None:
    for table in ("mensajes", "reacciones_mensaje"):
        op.execute(f"drop trigger if exists trg_{table}_actualizado on public.{table}")
    op.execute("drop trigger if exists trg_mensajes_tocar_actividad on public.mensajes")
    op.execute("drop function if exists public.tocar_actividad_conversacion()")
    op.execute(
        "alter table public.miembros_conversacion"
        " drop constraint if exists fk_miembros_ultimo_leido"
    )
    op.execute("drop table if exists public.reacciones_mensaje cascade")
    op.execute("drop table if exists public.versiones_mensaje cascade")
    op.execute("drop table if exists public.mensajes cascade")
