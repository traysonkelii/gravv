"""Every mapped column exists in the live schema with the same nullability, and every live column is mapped
unless it is a generated column or deliberately excluded."""

import warnings

from sqlalchemy import exc, inspect
from sqlalchemy.engine import Connection

from app.db.models import Base
from app.db.session import api_engine

# Columns that exist in the database but are intentionally unmapped.
UNMAPPED = {
    "contacts": {"search_vector"},
    "interactions": {"search_vector", "embedding"},
    "integrations": {"credentials_enc"},
    "ai_credentials": {"key_enc"},
}


def _columns(conn: Connection, table: str) -> dict[str, bool]:
    return {c["name"]: bool(c["nullable"]) for c in inspect(conn).get_columns(table)}


async def test_models_match_migrations() -> None:
    warnings.simplefilter("ignore", exc.SAWarning)  # citext reflects as an unknown type
    async with api_engine().connect() as conn:
        for table in Base.metadata.tables.values():
            live = await conn.run_sync(_columns, table.name)
            assert live, f"table {table.name} missing from database"
            mapped = {c.name: c.nullable for c in table.columns}
            missing = set(mapped) - set(live)
            assert not missing, f"{table.name}: columns in model but not in db: {missing}"
            extra = set(live) - set(mapped) - UNMAPPED.get(table.name, set())
            assert not extra, f"{table.name}: columns in db but not in model: {extra}"
            for name, nullable in mapped.items():
                assert live[name] == nullable, f"{table.name}.{name}: nullable model={nullable} db={live[name]}"
