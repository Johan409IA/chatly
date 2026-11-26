"""RLS para el arranque del chat privado (§7.2.1, Q20, Q146)

La Iteración 4 trajo `POST /api/messages/direct`: la conversación privada
nace al enviar el primer mensaje, con conversación + dos membresías + mensaje
en una misma transacción. Las políticas de `0007_rls` no contemplaban ese
arranque y lo bloqueaban en producción (42501):

1. `returning id` sobre `conversaciones` exige que la fila nueva pase la
   política SELECT (`conversaciones_select_backend_membresia` →
   `app.has_membership`), pero las membresías aún no existen en ese instante.
   Se resuelve en el repositorio generando el `id` en la aplicación y sin
   `RETURNING` (no requiere cambio de RLS).
2. La membresía del destinatario no pasaba `miembros_insert_backend`: la vía
   de administrador no aplica a chats directos y la vía bootstrap exige
   `usuario_id = current_actor`. Esta migración añade la vía
   `app.can_seed_direct_membership`: un actor verificado que forma parte de
   la pareja de un chat directo sin borrar puede sembrar ambas membresías
   mientras la conversación tenga menos de dos.

La vía nueva es más restrictiva que la de grupos: solo aplica a conversaciones
`direct`, solo para usuarios que están en la pareja registrada de la
conversación y solo mientras la conversación no tenga las dos membresías. No
permite añadir terceros ni operar sobre grupos.

Fuente: `docs/authorization-matrix.md` §3.3 y §5.4 (actualizados aquí).
"""

from alembic import op

revision = "0014_rls_chat_directo"
down_revision = "0013_descubrimiento_social"
branch_labels = None
depends_on = None

_FUNCION_SEED = """
create or replace function app.can_seed_direct_membership(
    p_conversacion_id uuid,
    p_usuario_id uuid
)
returns boolean
language sql
stable
security definer
set search_path = public, pg_temp
as $$
    select (
        (select app.is_verified_actor())
        and exists (
            select 1
            from public.conversaciones c
            where c.id = p_conversacion_id
              and c.tipo = 'direct'
              and c.eliminado_en is null
              and (select app.current_actor_id())
                  in (c.usuario_directo_menor, c.usuario_directo_mayor)
              and p_usuario_id in (c.usuario_directo_menor, c.usuario_directo_mayor)
              and (
                  select count(*)
                  from public.miembros_conversacion m
                  where m.conversacion_id = c.id
              ) < 2
        )
    );
$$;
"""

_POLITICA_MIEMBROS = """
create policy miembros_insert_backend on public.miembros_conversacion
    for insert to chatly_app
    with check (
        exists (
            select 1
            from public.perfiles p
            where p.id = usuario_id
              and p.correo_verificado_en is not null
              and p.eliminado_en is null
        )
        and (
            (select app.is_active_admin(conversacion_id))
            or (
                usuario_id = (select app.current_actor_id())
                and (select app.can_bootstrap_membership(conversacion_id, usuario_id))
            )
            or (select app.can_seed_direct_membership(conversacion_id, usuario_id))
        )
    )
"""

# Versión previa (0007_rls §2.2), para el downgrade.
_POLITICA_MIEMBROS_ORIGINAL = _POLITICA_MIEMBROS.replace(
    "            or (select app.can_seed_direct_membership(conversacion_id, usuario_id))\n",
    "",
)


def upgrade() -> None:
    op.execute(_FUNCION_SEED)
    op.execute("revoke all on function app.can_seed_direct_membership(uuid, uuid) from public")
    op.execute("grant execute on function app.can_seed_direct_membership(uuid, uuid) to chatly_app")
    op.execute("drop policy if exists miembros_insert_backend on public.miembros_conversacion")
    op.execute(_POLITICA_MIEMBROS)


def downgrade() -> None:
    op.execute("drop policy if exists miembros_insert_backend on public.miembros_conversacion")
    op.execute(_POLITICA_MIEMBROS_ORIGINAL)
    op.execute("drop function if exists app.can_seed_direct_membership(uuid, uuid)")
