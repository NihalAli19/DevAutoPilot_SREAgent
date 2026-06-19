"""Database service — async SQLAlchemy/asyncpg access, tenant-scoped queries."""
# TODO(plan: Phase 2) — async engine/session management and repositories.


class DBService:
    """Async data-access layer for relational + audit data."""
