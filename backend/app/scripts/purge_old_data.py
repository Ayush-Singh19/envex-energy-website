"""Delete data past its retention period (see app/services/retention_service.py).

    uv run python -m app.scripts.purge_old_data --dry-run   # show what would go
    uv run python -m app.scripts.purge_old_data             # delete it

Schedule it daily, e.g. a Render/Railway cron job running the second command.
"""

import argparse
import asyncio

from app.core.config import get_settings
from app.db.session import SessionLocal, engine
from app.services.retention_service import purge


async def _run(dry_run: bool) -> None:
    try:
        async with SessionLocal() as session:
            result = await purge(session, get_settings(), dry_run=dry_run)
    finally:
        await engine.dispose()
    verb = "Would delete" if dry_run else "Deleted"
    print(
        f"{verb}: {result.enquiries} enquiries, {result.audit_entries} audit entries, "
        f"{result.click_events} click events."
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--dry-run", action="store_true", help="Only count, delete nothing")
    asyncio.run(_run(parser.parse_args().dry_run))


if __name__ == "__main__":
    main()
