"""Tests for the reseed database utility module."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import reseed
from app.models.identity import Role, User, UserRole
from app.models.learning import Course
from app.models.wallet import WalletAccount

pytestmark = pytest.mark.integration


def test_parse_args_defaults():
    args = reseed.parse_args([])
    assert args.clean_all is False
    assert args.skip_seed is False


def test_parse_args_clean_all():
    args = reseed.parse_args(["--all"])
    assert args.clean_all is True
    assert args.skip_seed is False

    args_clean_all = reseed.parse_args(["--clean-all"])
    assert args_clean_all.clean_all is True


def test_parse_args_skip_seed():
    args = reseed.parse_args(["--skip-seed"])
    assert args.clean_all is False
    assert args.skip_seed is True


async def test_get_tables_to_truncate_preserves_users(session: AsyncSession):
    tables = await reseed.get_tables_to_truncate(session, preserve_users=True)
    assert "users" not in tables
    assert "roles" not in tables
    assert "user_roles" not in tables
    assert "sessions" not in tables
    assert "wallet_accounts" not in tables
    assert "alembic_version" not in tables
    # Non-user tables should be present in the truncate list if they exist in schema
    assert "courses" in tables or "exams" in tables or len(tables) > 0


async def test_get_tables_to_truncate_wipes_all(session: AsyncSession):
    tables = await reseed.get_tables_to_truncate(session, preserve_users=False)
    assert "alembic_version" not in tables
    assert "users" in tables
    assert "roles" in tables


async def test_clean_database_preserves_users_and_wipes_courses(session: AsyncSession):
    from app.core.security import hash_password

    # Create a test role and user
    role = (await session.execute(select(Role).where(Role.name == "teacher"))).scalar_one_or_none()
    if role is None:
        role = Role(name="teacher", description="Teacher")
        session.add(role)
        await session.flush()

    user = User(
        email="reseed_test_teacher@example.com",
        full_name="Guru Reseed",
        password_hash=hash_password("Pass123!"),
        chain_user_ref="0x" + "a" * 64,
        class_code="10A",
        class_type="IPA",
    )
    session.add(user)
    await session.flush()

    session.add(UserRole(user_id=user.id, role_id=role.id))
    wallet = WalletAccount(user_id=user.id, token_id=0, cached_balance=500)
    session.add(wallet)

    course = Course(
        owner_id=user.id,
        title="Kursus Uji Reseed",
        slug="kursus-uji-reseed",
        subject="Matematika",
        class_code="10A",
        class_type="IPA",
    )
    session.add(course)
    await session.flush()
    user_id = user.id
    course_id = course.id
    await session.commit()

    # Verify rows exist before clean
    u_before = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    c_before = (
        await session.execute(select(Course).where(Course.id == course_id))
    ).scalar_one_or_none()
    assert u_before is not None
    assert c_before is not None

    # Run clean_database using the active test session
    truncated = await reseed.clean_database(preserve_users=True, session=session)
    assert "courses" in truncated

    # Verify user still exists, course is gone, and wallet balance reset to 0
    u_after = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    c_after = (
        await session.execute(select(Course).where(Course.id == course_id))
    ).scalar_one_or_none()
    w_balance = (
        await session.execute(
            select(WalletAccount.cached_balance).where(WalletAccount.user_id == user_id)
        )
    ).scalar_one()

    assert u_after is not None
    assert u_after.email == "reseed_test_teacher@example.com"
    assert c_after is None
    assert w_balance == 0
    await session.commit()
