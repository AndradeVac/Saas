"""Fly release command: `python -m app.migrate` (instead of plain `alembic upgrade head`).

Rolling back to an older image after a deploy that ran a migration used to fail here with "Can't locate revision":
the old image does not know the newer revision stored in the database, so Fly aborted the rollback. Migrations are
written to be additive (new tables, nullable columns), so older code runs fine on a newer schema; in that case this
skips the upgrade and lets the rollback go through. See DEPLOY.md, "Voltar uma versão".
"""
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine

from app.core.config import settings


def main() -> int:
    config = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))
    known = {rev.revision for rev in ScriptDirectory.from_config(config).walk_revisions()}
    engine = create_engine(settings.database_url)
    with engine.connect() as connection:
        current = MigrationContext.configure(connection).get_current_revision()
    engine.dispose()
    if current and current not in known:
        print(f"Banco na revisão {current}, mais nova que esta imagem: é uma volta de versão. Migrações puladas.")
        return 0
    command.upgrade(config, "head")
    return 0


if __name__ == "__main__":
    sys.exit(main())
