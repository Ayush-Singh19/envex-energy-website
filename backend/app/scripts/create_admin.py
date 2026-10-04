"""Create an admin account, or reset an existing one's password (there is no public sign-up).

    uv run python -m app.scripts.create_admin --email owner@example.com --name "Owner"
    uv run python -m app.scripts.create_admin --email owner@example.com --reset

The password is asked for twice without echoing. For automation, pipe it in with
--password-stdin (never pass passwords as arguments: they end up in shell history).
Resetting also unlocks the account and signs out every existing session.
"""

import argparse
import asyncio
import getpass
import sys

from app.db.session import SessionLocal, engine
from app.services.auth_service import create_or_reset_admin


def _read_password(from_stdin: bool) -> str:
    if from_stdin:
        return sys.stdin.readline().rstrip("\r\n")
    first = getpass.getpass("Password: ")
    if getpass.getpass("Type it again: ") != first:
        sys.exit("Passwords don't match.")
    return first


async def _run(email: str, name: str | None, password: str, reset: bool) -> None:
    try:
        async with SessionLocal() as session:
            admin, created = await create_or_reset_admin(
                session, email=email, full_name=name, password=password, reset=reset
            )
    finally:
        await engine.dispose()
    verb = "Created" if created else "Reset password for"
    print(f"{verb} admin {admin.email} ({admin.full_name}).")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", help="Display name, e.g. 'Envex Owner'")
    parser.add_argument("--reset", action="store_true", help="Reset the password if it exists")
    parser.add_argument(
        "--password-stdin", action="store_true", help="Read the password from stdin"
    )
    args = parser.parse_args()

    password = _read_password(args.password_stdin)
    try:
        asyncio.run(_run(args.email, args.name, password, args.reset))
    except ValueError as exc:
        sys.exit(str(exc))


if __name__ == "__main__":
    main()
