"""Reseed the QLoot database with realistic curriculum and timeline data.

Preserves user accounts, credentials, and roles by default (matching the
'kecuali users data' requirement). It cleans out dummy/stale learning, exams,
quests, rooms, community, and wallet data, then invokes the complete realistic
seeder suite (curriculum catalogue, quests, monthly timeline 100-200 records/mo
from 2025, certificates, etc.).

Usage:
    python -m app.db.reseed
    python -m app.db.reseed --all      # Also wipes user accounts (clean slate)
    python -m app.db.reseed --skip-seed # Only clears non-user data
    make reseed
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import configure_logging, get_logger
from app.db.session import session_scope

log = get_logger("reseed")

# Core identity tables that should NEVER be wiped when preserve_users=True.
PRESERVED_TABLES = {
    "alembic_version",
    "users",
    "roles",
    "user_roles",
    "sessions",
    "password_reset_tokens",
    "email_change_tokens",
    "wallet_accounts",
}


async def get_tables_to_truncate(session: AsyncSession, preserve_users: bool = True) -> list[str]:
    """Return all public base tables that should be truncated."""
    query = text(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_type = 'BASE TABLE'
        ORDER BY table_name;
        """
    )
    result = await session.execute(query)
    all_tables = [row[0] for row in result.fetchall()]

    if preserve_users:
        return [t for t in all_tables if t not in PRESERVED_TABLES]
    return [t for t in all_tables if t != "alembic_version"]


async def _clean_database_impl(session: AsyncSession, preserve_users: bool) -> list[str]:
    from app.models.identity import User
    from app.models.wallet import WalletAccount
    from app.services.wallet_service import default_wallet_address

    to_truncate = await get_tables_to_truncate(session, preserve_users=preserve_users)
    if not to_truncate:
        log.info("reseed_no_tables_to_truncate")
        return []

    quoted_tables = ", ".join(f'"{t}"' for t in to_truncate)
    truncate_sql = f"TRUNCATE TABLE {quoted_tables} RESTART IDENTITY CASCADE;"
    log.info(
        "reseed_truncating_tables",
        count=len(to_truncate),
        preserve_users=preserve_users,
    )
    await session.execute(text(truncate_sql))

    if preserve_users:
        # Reset wallet account balances to zero so the new seed can credit cleanly.
        await session.execute(text("UPDATE wallet_accounts SET cached_balance = 0;"))

        # Ensure every existing user has a wallet account.
        existing_wallet_user_ids = {
            uid for (uid,) in (await session.execute(select(WalletAccount.user_id))).all()
        }
        users = (await session.execute(select(User))).scalars().all()
        for u in users:
            if u.id not in existing_wallet_user_ids:
                session.add(
                    WalletAccount(
                        user_id=u.id,
                        token_id=0,
                        withdrawal_address=default_wallet_address() or None,
                    )
                )
        await session.flush()

    log.info("reseed_clean_complete", truncated=len(to_truncate))
    return to_truncate


async def clean_database(
    preserve_users: bool = True, session: AsyncSession | None = None
) -> list[str]:
    """Truncate tables with CASCADE while optionally preserving user accounts."""
    if session is not None:
        return await _clean_database_impl(session, preserve_users)
    async with session_scope() as sess:
        return await _clean_database_impl(sess, preserve_users)


async def run_reseed(preserve_users: bool = True, run_seed: bool = True) -> None:
    """Execute truncation and then the full realistic seed suite."""
    from app.db.seed import main as seed_main

    log.info(
        "reseed_start",
        preserve_users=preserve_users,
        run_seed=run_seed,
    )

    truncated = await clean_database(preserve_users=preserve_users)
    log.info("reseed_tables_cleared", count=len(truncated))

    if run_seed:
        log.info("reseed_running_seed_suite")
        await seed_main()
        log.info("reseed_seed_suite_finished")

    log.info("reseed_complete")


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reseed the QLoot database with realistic curriculum and timeline data."
    )
    parser.add_argument(
        "--all",
        "--clean-all",
        action="store_true",
        dest="clean_all",
        help=(
            "Clean all tables including users and roles (clean slate reseed). "
            "Default preserves users."
        ),
    )
    parser.add_argument(
        "--skip-seed",
        action="store_true",
        dest="skip_seed",
        help="Only truncate tables, do not run the seed suite.",
    )
    return parser.parse_args(args)


async def main() -> None:
    configure_logging()
    args = parse_args(sys.argv[1:])
    preserve_users = not args.clean_all
    run_seed = not args.skip_seed

    await run_reseed(preserve_users=preserve_users, run_seed=run_seed)


if __name__ == "__main__":
    asyncio.run(main())
