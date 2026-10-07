"""CLI: create the first administrator (or a lecturer) account.

Usage (from the backend directory, with the venv active):

    $env:DATABASE_URL="postgresql+asyncpg://course_engine:course_engine@localhost:5432/course_engine"
    python scripts/create_admin.py --email admin@example.com --full-name "Admin"

The password is prompted interactively (hidden) and is never written to
the shell history or the command line. Alternatively, pass
--password explicitly for non-interactive provisioning.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import sys
from pathlib import Path

# Allow direct `python scripts/create_admin.py` execution.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings  # noqa: E402
from app.db.database import create_database_engine  # noqa: E402
from app.db.repositories.users import UserRepository  # noqa: E402
from app.models.user import UserRole  # noqa: E402
from app.services.auth.service import AuthService  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker  # noqa: E402


async def run(*, email: str, full_name: str, role: UserRole,
              password: str | None) -> int:
    settings = Settings()
    engine = create_database_engine(settings)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    if password is None:
        password = getpass.getpass("Password: ")
        if not password:
            print("Password must not be empty.")
            await engine.dispose()
            return 1

    async with session_factory() as session:
        repository = UserRepository(session)
        existing = await repository.get_by_email(email)
        if existing is not None:
            print(f"User {email!r} already exists (id={existing.id}, "
                  f"role={existing.role.value}).")
            await engine.dispose()
            return 1

        user = await AuthService(repository).create_user(
            email=email,
            password=password,
            full_name=full_name,
            role=role,
        )
        print(f"Created {role.value} user id={user.id} "
              f"email={user.email!r} full_name={user.full_name!r}")

    await engine.dispose()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--full-name", default="Administrator")
    parser.add_argument(
        "--role",
        choices=["admin", "lecturer"],
        default="admin",
    )
    parser.add_argument("--password", default=None, help="Non-interactive use")
    args = parser.parse_args()

    role = UserRole.ADMIN if args.role == "admin" else UserRole.LECTURER

    try:
        return asyncio.run(
            run(
                email=args.email,
                full_name=args.full_name,
                role=role,
                password=args.password,
            )
        )
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())