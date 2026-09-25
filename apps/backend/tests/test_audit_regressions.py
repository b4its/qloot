"""Regression tests for bugs found during the code audit.

Each test here corresponds to a specific fix:
  - grading denominator must include skipped questions
  - answers may not be injected for questions from another exam
  - repeated transfers to the same recipient must not collide
  - room ranking must not include scores from unrelated exams
  - global ranking must use best-score-per-exam (no retry double counting)
  - admin reward retry must carry the real user reference
"""

from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.integration


async def _register(client, email, role="student", name="Test User"):
    from tests.helpers import register_actor

    return await register_actor(client, email, role, full_name=name)


async def _make_exam_with_questions(client, n=2, max_attempts=10):
    exam = await client.post(
        "/api/v1/exams", json={"title": "Audit Exam", "max_attempts": max_attempts}
    )
    assert exam.status_code == 201
    exam_id = exam.json()["id"]
    qids = []
    for i in range(n):
        q = await client.post(
            f"/api/v1/exams/{exam_id}/questions",
            json={"prompt": f"Question {i}?", "correct_answer": "reference answer", "position": i},
        )
        assert q.status_code == 201, q.text
        qids.append(q.json()["id"])
    await client.post(f"/api/v1/exams/{exam_id}/publish")
    return exam_id, qids


async def test_skipping_questions_lowers_the_score(client):
    """A student answering 1 of 2 questions perfectly must score ~50%, not 100%."""
    await _register(client, "t_skip@ex.com", "teacher")
    exam_id, qids = await _make_exam_with_questions(client, n=2)
    await client.post("/api/v1/auth/logout")

    await _register(client, "s_skip@ex.com", "student")
    attempt = await client.post(f"/api/v1/exams/{exam_id}/attempts")
    attempt_id = attempt.json()["id"]
    # Answer only the first question.
    await client.put(
        f"/api/v1/attempts/{attempt_id}/answers/{qids[0]}",
        json={"answer_text": "reference answer"},
    )
    await client.post(f"/api/v1/attempts/{attempt_id}/submit")
    grade = await client.post("/api/v1/ai/grade", json={"attempt_id": attempt_id})
    assert grade.status_code == 200

    result = await client.get(f"/api/v1/attempts/{attempt_id}/result")
    score_bp = result.json()["attempt"]["score_bp"]
    # The unanswered question must count against the total (<= ~5000 bp, not 10000).
    assert score_bp is not None
    assert score_bp <= 6000, f"skipped question not counted against score: {score_bp}"


async def test_cannot_answer_question_from_another_exam(client):
    await _register(client, "t_x@ex.com", "teacher")
    exam_a, _ = await _make_exam_with_questions(client, n=1)
    exam_b, qids_b = await _make_exam_with_questions(client, n=1)
    await client.post("/api/v1/auth/logout")

    await _register(client, "s_x@ex.com", "student")
    attempt = await client.post(f"/api/v1/exams/{exam_a}/attempts")
    attempt_id = attempt.json()["id"]
    # Try to answer a question that belongs to exam_b.
    resp = await client.put(
        f"/api/v1/attempts/{attempt_id}/answers/{qids_b[0]}",
        json={"answer_text": "injected"},
    )
    assert resp.status_code == 404


async def test_debit_for_transfer_is_idempotent_per_reference(engine):
    """RewardEngine.debit_for_transfer debits once per reference_id (all balance
    mutations go through the engine, idempotently)."""
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.core.security import hash_password
    from app.models.identity import User
    from app.models.wallet import WalletLedgerEntry
    from app.services.reward_engine import RewardEngine

    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as s:
        user = User(
            email=f"debit_idem_{uuid.uuid4().hex[:6]}@ex.com",
            full_name="Debit Idem",
            password_hash=hash_password("Password123!"),
            chain_user_ref="0x" + uuid.uuid4().hex,
        )
        s.add(user)
        await s.flush()
        eng = RewardEngine(s)
        await eng.credit(
            user=user,
            amount=100,
            reference_type="testfund",
            reference_id="seed-debit",
            reward_key_value="seed-debit",
            token_id=0,
        )
        first = await eng.debit_for_transfer(user=user, amount=30, reference_id="ref-X")
        second = await eng.debit_for_transfer(user=user, amount=30, reference_id="ref-X")
        assert first.id == second.id  # idempotent: no second entry
        rows = (
            await s.execute(
                select(WalletLedgerEntry).where(
                    WalletLedgerEntry.reference_id == "ref-X",
                    WalletLedgerEntry.entry_type == "debit",
                )
            )
        ).scalars().all()
        assert len(rows) == 1
        assert await eng.balance(user.id) == 70
        await s.rollback()


async def test_repeated_transfers_do_not_collide(client, engine):
    """Two identical transfers to the same recipient must both succeed."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.models.identity import User
    from app.services.reward_engine import RewardEngine

    await _register(client, "t_tr@ex.com", "teacher")
    exam_id, _ = await _make_exam_with_questions(client, n=1)
    await client.post("/api/v1/auth/logout")

    # Sender gets funded via the ledger, recipient is a second student.
    await _register(client, "s_send@ex.com", "student", "Sender")
    sender_me = await client.get("/api/v1/auth/me")
    sender_id = sender_me.json()["id"]
    await client.post("/api/v1/auth/logout")
    await _register(client, "s_recv@ex.com", "student", "Receiver")
    recv_me = await client.get("/api/v1/auth/me")
    recv_id = recv_me.json()["id"]
    await client.post("/api/v1/auth/logout")

    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as s:
        sender = await s.get(User, uuid.UUID(sender_id))
        engine_ = RewardEngine(s)
        await engine_.credit(
            user=sender,
            amount=100,
            reference_type="testfund",
            reference_id="seed",
            reward_key_value="seed",
            token_id=0,
        )
        await s.commit()

    await client.post(
        "/api/v1/auth/login", json={"email": "s_send@ex.com", "password": "Password123!"}
    )
    for _ in range(2):
        r = await client.post(
            "/api/v1/wallet/transfers", json={"to_user_id": recv_id, "amount": 10}
        )
        assert r.status_code == 200, r.text
    wallet = await client.get("/api/v1/wallet")
    assert wallet.json()["available"] == 80


async def test_transfer_recipient_search(client):
    """Recipient search returns other active users and excludes the caller."""
    await _register(client, "s_seeker@ex.com", "student", "Seeker")
    me = (await client.get("/api/v1/auth/me")).json()["id"]
    await client.post("/api/v1/auth/logout")
    await _register(client, "s_target@ex.com", "student", "Targetted Name")
    await client.post("/api/v1/auth/logout")

    await client.post(
        "/api/v1/auth/login", json={"email": "s_seeker@ex.com", "password": "Password123!"}
    )
    r = await client.get("/api/v1/wallet/transfer-recipients?q=targetted")
    assert r.status_code == 200, r.text
    ids = [x["user_id"] for x in r.json()]
    assert me not in ids
    assert any(x["full_name"] == "Targetted Name" for x in r.json())
    # Raw email is never returned (WEB3-12).
    assert all("email" not in x for x in r.json())
    assert all("email_masked" in x for x in r.json())


async def test_room_ranking_excludes_unrelated_exams(client, engine):
    """Scores from exams not tied to a room must not appear in its ranking."""

    # Teacher creates a room and an exam NOT linked to it.
    await _register(client, "t_room@ex.com", "teacher")
    room = await client.post("/api/v1/rooms", json={"name": "Audit Room"})
    room_id = room.json()["id"]
    await client.post(f"/api/v1/rooms/{room_id}/open")
    exam_id, qids = await _make_exam_with_questions(client, n=1)
    await client.post("/api/v1/auth/logout")

    await _register(client, "s_room@ex.com", "student")
    me = await client.get("/api/v1/auth/me")
    student_id = me.json()["id"]
    await client.post(f"/api/v1/rooms/{room_id}/join")
    attempt = await client.post(f"/api/v1/exams/{exam_id}/attempts")
    attempt_id = attempt.json()["id"]
    await client.put(
        f"/api/v1/attempts/{attempt_id}/answers/{qids[0]}", json={"answer_text": "reference answer"}
    )
    await client.post(f"/api/v1/attempts/{attempt_id}/submit")
    await client.post("/api/v1/ai/grade", json={"attempt_id": attempt_id})

    rank = await client.get(f"/api/v1/rankings/rooms/{room_id}")
    assert rank.status_code == 200
    entries = {e["user_id"]: e["score_bp"] for e in rank.json()["entries"]}
    # The student is a member, but has no exam tied to the room -> score 0.
    assert entries.get(student_id, 0) == 0


async def test_global_ranking_uses_best_per_exam(client):
    """Retrying the same exam must not double-count in the global ranking."""
    await _register(client, "t_g@ex.com", "teacher")
    exam_id, qids = await _make_exam_with_questions(client, n=1)
    await client.post("/api/v1/auth/logout")

    await _register(client, "s_g@ex.com", "student")
    me = await client.get("/api/v1/auth/me")
    student_id = me.json()["id"]

    # Two attempts on the same exam.
    for _ in range(2):
        attempt = await client.post(f"/api/v1/exams/{exam_id}/attempts")
        attempt_id = attempt.json()["id"]
        await client.put(
            f"/api/v1/attempts/{attempt_id}/answers/{qids[0]}",
            json={"answer_text": "reference answer"},
        )
        await client.post(f"/api/v1/attempts/{attempt_id}/submit")
        await client.post("/api/v1/ai/grade", json={"attempt_id": attempt_id})

    rank = await client.get("/api/v1/rankings/global")
    entry = next(
        (e for e in rank.json()["entries"] if e["user_id"] == student_id),
        None,
    )
    assert entry is not None
    # One exam answered -> total equals a single attempt's score (<= 10000).
    assert entry["score_bp"] <= 10000


async def test_reserved_domain_email_does_not_break_user_listing(client, engine):
    """A legacy email with a reserved TLD must not turn reads into a 500."""
    from sqlalchemy import select, update
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.models.identity import Role, User, UserRole
    from tests.helpers import register_actor

    r = await register_actor(client, "legacy_admin@example.com", "teacher")
    user_id = uuid.UUID(r["id"])

    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as s:
        # Promote to admin and set a reserved-domain email (simulating legacy data).
        admin_role = (await s.execute(select(Role).where(Role.name == "admin"))).scalar_one()
        await s.execute(select(UserRole).where(UserRole.user_id == user_id))
        for ur in (
            (await s.execute(select(UserRole).where(UserRole.user_id == user_id))).scalars().all()
        ):
            await s.delete(ur)
        await s.flush()
        s.add(UserRole(user_id=user_id, role_id=admin_role.id))
        await s.execute(update(User).where(User.id == user_id).values(email="legacy@qloot.local"))
        await s.commit()

    listed = await client.get("/api/v1/admin/users")
    assert listed.status_code == 200, listed.text
    assert any(u["email"] == "legacy@qloot.local" for u in listed.json())


async def test_material_ask_and_summary_are_access_controlled(client):
    """A material's AI summary/Q&A must not be readable by unrelated users."""
    import io

    from tests.pdf_util import make_pdf

    # Owner uploads a private (course-less) material.
    await _register(client, "owner_mat@ex.com", "teacher")
    pdf = make_pdf("Fotosintesis terjadi di kloroplas dan menghasilkan glukosa serta oksigen.")
    up = await client.post(
        "/api/v1/materials/upload",
        files={"file": ("bio.pdf", io.BytesIO(pdf), "application/pdf")},
    )
    assert up.status_code == 201, up.text
    material_id = up.json()["id"]

    # Owner can summarise and ask.
    own_sum = await client.get(f"/api/v1/materials/{material_id}/summary")
    assert own_sum.status_code == 200, own_sum.text
    own_ask = await client.post(
        f"/api/v1/materials/{material_id}/ask", json={"question": "Di mana fotosintesis terjadi?"}
    )
    assert own_ask.status_code == 200, own_ask.text

    # A different teacher is neither owner nor enrolled -> forbidden.
    await client.post("/api/v1/auth/logout")
    await _register(client, "intruder_mat@ex.com", "teacher")
    other_sum = await client.get(f"/api/v1/materials/{material_id}/summary")
    assert other_sum.status_code == 403
    other_ask = await client.post(
        f"/api/v1/materials/{material_id}/ask", json={"question": "Di mana fotosintesis terjadi?"}
    )
    assert other_ask.status_code == 403


async def test_admin_reward_retry_resets_existing_outbox(client, engine):
    """Retrying a reward that already has an outbox row must not crash.

    The retry used to set the NOT NULL ``available_at`` column to None,
    raising a constraint violation for the normal retry case.
    """
    import uuid as _uuid

    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.models.identity import Role, UserRole
    from app.models.wallet import RewardAllocation, TransactionOutbox
    from app.services.keys import tx_idempotency_key

    # Register a teacher, promote to admin.
    from tests.helpers import register_actor

    r = await register_actor(client, "retry_admin@ex.com", "teacher")
    admin_id = _uuid.UUID(r["id"])
    student = await _register(client, "retry_student@ex.com", "student")
    student_id = _uuid.UUID(student["id"])

    sm = async_sessionmaker(engine, expire_on_commit=False)
    alloc_id = _uuid.uuid4()
    reward_key = f"rk-{alloc_id.hex[:8]}"
    async with sm() as s:
        admin_role = (await s.execute(select(Role).where(Role.name == "admin"))).scalar_one()
        for ur in (
            (await s.execute(select(UserRole).where(UserRole.user_id == admin_id))).scalars().all()
        ):
            await s.delete(ur)
        await s.flush()
        s.add(UserRole(user_id=admin_id, role_id=admin_role.id))
        # A pending reward allocation whose outbox row already exists (failed).
        s.add(
            RewardAllocation(
                id=alloc_id,
                user_id=student_id,
                reward_key=reward_key,
                reward_type="quest_rank",
                amount=50,
                status="pending",
                token_id=0,
            )
        )
        s.add(
            TransactionOutbox(
                topic="reward",
                idempotency_key=tx_idempotency_key("reward", reward_key),
                payload={"allocation_id": str(alloc_id)},
                status="failed",
                attempts=3,
            )
        )
        await s.commit()

    # Re-login as the promoted admin so the request carries the admin role.
    await client.post("/api/v1/auth/logout")
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "retry_admin@ex.com", "password": "Password123!"},
    )
    assert login.status_code == 200, login.text

    resp = await client.post(f"/api/v1/admin/rewards/{alloc_id}/retry")
    assert resp.status_code < 500, resp.text
    assert resp.status_code == 200, resp.text

    # Clean up so the seeded outbox/allocation do not leak into other tests
    # (the suite shares one database).
    from sqlalchemy import delete

    from app.models.wallet import BlockchainTransaction as _BT
    from app.models.wallet import WalletLedgerEntry as _LE

    async with sm() as s:
        await s.execute(
            delete(TransactionOutbox).where(
                TransactionOutbox.idempotency_key == tx_idempotency_key("reward", reward_key)
            )
        )
        await s.execute(delete(RewardAllocation).where(RewardAllocation.id == alloc_id))
        await s.execute(delete(_LE).where(_LE.reference_id == str(alloc_id)))
        await s.execute(
            delete(_BT).where(_BT.idempotency_key == tx_idempotency_key("reward", reward_key))
        )
        await s.commit()


async def test_admin_manual_reward_adjustment_is_idempotent_and_audited(client):
    """WEB3-14: an admin adjustment writes one ledger entry + an audit row, and
    a repeated call with the same idempotency key does not double-apply."""
    from sqlalchemy import select

    from app.models.identity import AuditLog
    from app.models.wallet import WalletLedgerEntry

    await _register(client, "adj_target@ex.com", "student")
    target_id = (await client.get("/api/v1/auth/me")).json()["id"]
    await client.post("/api/v1/auth/logout")

    await _register(client, "adj_admin@ex.com", "admin")
    payload = {
        "user_id": target_id,
        "amount": 250,
        "reason": "Kompetisi sekolah",
        "idempotency_key": "adj-key-0001",
    }
    first = await client.post("/api/v1/admin/rewards/adjust", json=payload)
    assert first.status_code == 200, first.text

    # Repeat with the same key -> no second ledger entry.
    second = await client.post("/api/v1/admin/rewards/adjust", json=payload)
    assert second.status_code == 200, second.text

    sm = client._sm  # type: ignore[attr-defined]
    async with sm() as s:
        entries = (
            await s.execute(
                select(WalletLedgerEntry).where(
                    WalletLedgerEntry.reference_type == "admin_adjustment",
                    WalletLedgerEntry.reference_id == "adj-key-0001",
                )
            )
        ).scalars().all()
        audits = (
            await s.execute(
                select(AuditLog).where(
                    AuditLog.action == "reward.adjust",
                    AuditLog.entity_id == target_id,
                )
            )
        ).scalars().all()
    assert len(entries) == 1, "adjustment must be idempotent"
    assert entries[0].amount == 250
    assert len(audits) >= 1


async def test_failed_transactions_view_consolidates_terminal_failures(client, engine):
    """C17: admin failed-transactions view lists terminal failures."""
    await _register(client, "fail_view_a@ex.com", "admin")
    r = await client.get("/api/v1/blockchain/transactions/failed")
    assert r.status_code == 200, r.text
    # Shape check: every row carries the failure fields the UI renders.
    for row in r.json():
        assert {"id", "method", "status", "error_code"} <= set(row)


async def _audit_rows(client, action):
    from sqlalchemy import select

    from app.models.identity import AuditLog

    sm = client._sm  # type: ignore[attr-defined]
    async with sm() as s:
        return (
            await s.execute(select(AuditLog).where(AuditLog.action == action))
        ).scalars().all()


async def test_successful_login_is_audited_with_request_id(client):
    """AUTH-05: a successful login writes an ``auth.login`` audit row, and the
    row carries the request_id bound by the request-context middleware."""
    await _register(client, "audit_login@ex.com", "student")
    await client.post("/api/v1/auth/logout")
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "audit_login@ex.com", "password": "Password123!"},
    )
    assert login.status_code == 200, login.text

    rows = await _audit_rows(client, "auth.login")
    assert len(rows) >= 1, "successful login must be audited"
    assert all(r.request_id for r in rows), "audit row must carry a request_id"


async def test_failed_login_is_audited_even_when_request_fails(client):
    """AUTH-05: a failed login is persisted even though the endpoint raises 401
    (the audit row must survive the transaction rollback)."""
    await _register(client, "audit_fail@ex.com", "student")
    await client.post("/api/v1/auth/logout")

    bad = await client.post(
        "/api/v1/auth/login",
        json={"email": "audit_fail@ex.com", "password": "wrong-password"},
    )
    assert bad.status_code == 401, bad.text

    rows = await _audit_rows(client, "auth.login_failed")
    assert len(rows) >= 1, "failed login must be audited despite the 401"


async def test_logout_all_is_audited(client):
    """AUTH-05: sign-out-everywhere writes an ``auth.logout_all`` audit row."""
    await _register(client, "audit_logoutall@ex.com", "student")
    before = len(await _audit_rows(client, "auth.logout_all"))
    r = await client.post("/api/v1/auth/logout-all")
    assert r.status_code == 200, r.text
    after = await _audit_rows(client, "auth.logout_all")
    assert len(after) == before + 1
    assert after[-1].actor_id is not None


async def test_password_reset_is_audited(client):
    """AUTH-05: a completed password reset writes ``auth.password_reset``."""
    await _register(client, "audit_reset@ex.com", "student")
    await client.post("/api/v1/auth/logout")
    forgot = await client.post(
        "/api/v1/auth/forgot-password", json={"email": "audit_reset@ex.com"}
    )
    token = forgot.json()["reset_token"]
    assert token
    r = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": "NewPassword123!"},
    )
    assert r.status_code == 200, r.text
    rows = await _audit_rows(client, "auth.password_reset")
    assert len(rows) >= 1


async def test_admin_audit_endpoint_exposes_and_filters_request_id(client):
    """AUTH-05: the admin audit endpoint returns request_id and can filter by
    action so auth events are queryable."""
    await _register(client, "audit_admin2@ex.com", "admin")
    all_rows = await client.get("/api/v1/admin/audit-logs?limit=20")
    assert all_rows.status_code == 200, all_rows.text
    assert "request_id" in all_rows.json()[0]

    filtered = await client.get("/api/v1/admin/audit-logs?action=auth.login&limit=20")
    assert filtered.status_code == 200, filtered.text
    assert all(row["action"] == "auth.login" for row in filtered.json())


async def test_admin_mutations_carry_request_id(client):
    """AUTH-05: admin audit writes persist the request_id from context (it was
    previously only set by the seeder)."""
    from sqlalchemy import select

    from app.models.identity import AuditLog

    await _register(client, "audit_admin3@ex.com", "admin")
    await client.post(
        "/api/v1/admin/users",
        json={
            "email": "created_by_admin_audit@ex.com",
            "full_name": "Created",
            "password": "Password123!",
            "role": "teacher",
        },
    )
    sm = client._sm  # type: ignore[attr-defined]
    async with sm() as s:
        row = (
            await s.execute(
                select(AuditLog).where(AuditLog.action == "user.create").limit(1)
            )
        ).scalar_one_or_none()
    assert row is not None
    assert row.request_id, "admin audit row must carry a request_id"


async def test_admin_list_endpoints_report_total_count(client):
    """AUTH-11: paginated admin lists expose X-Total-Count so the UI can show
    real totals instead of guessing from a full page."""
    await _register(client, "total_admin@ex.com", "admin")
    for path in ("/api/v1/admin/users?limit=1", "/api/v1/admin/audit-logs?limit=1"):
        resp = await client.get(path)
        assert resp.status_code == 200, resp.text
        total = resp.headers.get("X-Total-Count")
        assert total is not None and int(total) >= 1, f"missing total for {path}"

    filtered = await client.get("/api/v1/admin/audit-logs?limit=1&action=auth.login")
    assert filtered.status_code == 200
    assert int(filtered.headers["X-Total-Count"]) >= 1


async def test_admin_config_summary_excludes_secrets(client):
    """AUTH-11: /admin/config returns a non-secret runtime summary."""
    await _register(client, "cfg_admin@ex.com", "admin")
    resp = await client.get("/api/v1/admin/config")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert {"env", "ai_provider", "blockchain", "reward_ranks"} <= set(body)
    # No secret-bearing keys leak into the summary.
    leaked = {"session_secret", "database_url", "redis_url", "rpc_url", "minio_secret_key"}
    assert not (leaked & set(body))


def test_admin_reward_cancel_route_is_not_hijacked():
    """Regression: a stray decorator once made POST /admin/rewards/{id}/cancel
    resolve to list_withdrawals instead of cancel_reward. Assert the route is
    bound to the intended handler."""
    from app.main import app

    spec = app.openapi()
    op = spec["paths"]["/api/v1/admin/rewards/{reward_id}/cancel"]["post"]
    assert op["operationId"].startswith("cancel_reward"), op["operationId"]
    # And the withdrawals list must stay a GET on its own path.
    wd = spec["paths"]["/api/v1/admin/withdrawals"]
    assert set(wd) == {"get"}, wd
    assert wd["get"]["operationId"].startswith("list_withdrawals")


async def test_withdrawal_review_audit_carries_request_id(client):
    """C60 invariant: an admin withdrawal approval writes an AuditLog row that
    carries the request_id from the request context."""
    from sqlalchemy import delete, select

    from app.models.identity import AuditLog

    await _register(client, "wd_audit_user@ex.com")
    me = (await client.get("/api/v1/auth/me")).json()
    await client.post("/api/v1/auth/logout")

    await _register(client, "wd_audit_admin@ex.com", "admin")
    # Credit the student so a withdrawal can be requested.
    await client.post(
        "/api/v1/admin/rewards/adjust",
        json={
            "user_id": me["id"],
            "amount": 500,
            "reason": "seed for withdrawal audit",
            "idempotency_key": "wd-audit-seed",
        },
    )
    await client.post("/api/v1/auth/logout")

    await client.post(
        "/api/v1/auth/login", json={"email": "wd_audit_user@ex.com", "password": "Password123!"}
    )
    created = await client.post(
        "/api/v1/wallet/withdrawals",
        json={"amount": 100, "destination_address": "0x" + "1" * 40},
    )
    assert created.status_code in (200, 201), created.text
    wid = created.json()["id"]
    await client.post("/api/v1/auth/logout")

    await client.post(
        "/api/v1/auth/login", json={"email": "wd_audit_admin@ex.com", "password": "Password123!"}
    )
    approved = await client.post(f"/api/v1/admin/withdrawals/{wid}/approve")
    assert approved.status_code == 200, approved.text

    sm = client._sm  # type: ignore[attr-defined]
    async with sm() as s:
        row = (
            await s.execute(
                select(AuditLog).where(
                    AuditLog.action == "withdrawal.approve",
                    AuditLog.entity_id == wid,
                )
            )
        ).scalar_one_or_none()
    assert row is not None
    assert row.request_id, "withdrawal audit row must carry request_id"

    # Clean up so sibling tests that count withdrawal rows globally stay valid.
    from app.models.wallet import TransactionOutbox, WithdrawalRequest
    from app.services.keys import tx_idempotency_key

    async with sm() as s:
        await s.execute(
            delete(TransactionOutbox).where(
                TransactionOutbox.idempotency_key
                == tx_idempotency_key("withdrawal", wid)
            )
        )
        await s.execute(
            delete(WithdrawalRequest).where(WithdrawalRequest.id == uuid.UUID(wid))
        )
        await s.commit()
