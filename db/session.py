"""Backward-compatible DB exports.

This project uses the async SQLAlchemy engine/session defined in `db.base`.
Some older modules historically imported `db.session`.
"""

from db.base import Base, engine, get_db
