"""Base declarativa y mixins comunes de los modelos de Chatly.

Convenciones (AGENTS.md):
- Tablas y columnas en español.
- Clases, funciones y variables en inglés.
- Constraints e índices con prefijos `pk_`, `fk_`, `uq_`, `ck_`, `ix_`.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, MetaData, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func

NAMING_CONVENTION = {
    "pk": "pk_%(table_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "ix": "ix_%(table_name)s_%(column_0_name)s",
}


class Base(DeclarativeBase):
    """Base declarativa con convención de nombres para constraints e índices."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map = {datetime: DateTime(timezone=True)}


class UuidPkMixin:
    """Clave primaria UUID generada por la base de datos."""

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )


class TimestampsMixin:
    """Fechas de creación y actualización (`timestamptz`)."""

    creado_en: Mapped[datetime] = mapped_column(server_default=func.now())
    actualizado_en: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class SoftDeleteMixin:
    """Borrado lógico: filas con `eliminado_en` no nulo están eliminadas."""

    eliminado_en: Mapped[datetime | None] = mapped_column(default=None)


class AuditMixin:
    """Actor técnico que creó/actualizó la fila (UUID del usuario o None)."""

    creado_por: Mapped[uuid.UUID | None] = mapped_column(default=None)
    actualizado_por: Mapped[uuid.UUID | None] = mapped_column(default=None)
