from enum import StrEnum

from sqlalchemy import CheckConstraint, MetaData
from sqlalchemy.orm import DeclarativeBase

# Nombres fijos para índices y constraints, así Alembic genera migraciones estables
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def enum_check(column: str, enum_cls: type[StrEnum], name: str) -> CheckConstraint:
    """Limita una columna de texto a los valores del enum."""
    allowed = ", ".join(f"'{item.value}'" for item in enum_cls)
    return CheckConstraint(f"{column} IN ({allowed})", name=name)
