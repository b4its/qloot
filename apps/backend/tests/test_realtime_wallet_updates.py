"""Realtime wallet updates over user WebSocket stream (GAME-14)."""

from __future__ import annotations

import warnings

import pytest
from starlette.testclient import TestClient

from app.main import app
from app.services.reward_engine import RewardEngine

pytestmark = pytest.mark.integration


def _ws_client() -> TestClient:
    warnings.filterwarnings("ignore", category=DeprecationWarning, module="starlette.testclient")
    warnings.filterwarnings("ignore", category=UserWarning, module="starlette.testclient")
    return TestClient(app)


async def _register_and_token(client, email: str, role: str = "student", **kw) -> tuple[str, dict]:
    from tests.helpers import register_actor

    user = await register_actor(client, email, role, **kw)
    cookie = client.cookies.get("qloot_session")
    assert cookie, "login must set the session cookie"
    return cookie, user


async def test_ws_receives_wallet_update_on_task_completion(client):
    # 1. Register teacher to create an honor-system task
    await _register_and_token(client, "rt_teacher@ex.com", "teacher")
    task_res = await client.post(
        "/api/v1/tasks",
        json={"title": "Misi Harian Cepat", "kind": "daily", "reward_amount": 30},
    )
    assert task_res.status_code == 201, task_res.text
    task_id = task_res.json()["id"]

    await client.post("/api/v1/auth/logout")

    # 2. Register student and connect WS
    token, student = await _register_and_token(client, "rt_student@ex.com", "student")

    with _ws_client() as tc:
        with tc.websocket_connect(f"/api/v1/ws/notifications?token={token}") as ws:
            # Complete the task via HTTP
            res = await client.post(f"/api/v1/tasks/{task_id}/complete")
            assert res.status_code == 200, res.text

            # We should receive the wallet.updated event and the notification
            received = []
            for _ in range(2):
                frame = ws.receive_json()
                received.append(frame)

            types = {f["type"] for f in received}
            assert "wallet.updated" in types
            assert "notification" in types

            wallet_frame = next(f for f in received if f["type"] == "wallet.updated")
            assert wallet_frame["asset"] == "OPT"
            assert wallet_frame["balance"] == 30
            assert wallet_frame["amount"] == 30
            assert wallet_frame["entry_type"] == "credit"
            assert wallet_frame["reference_type"] == "task"


async def test_ws_receives_wallet_update_on_asset_credit_and_debit(client, session):
    token, student = await _register_and_token(client, "ws_asset_user@ex.com", "student")
    user_id = student["id"]

    with _ws_client() as tc:
        with tc.websocket_connect(f"/api/v1/ws/notifications?token={token}") as ws:
            engine = RewardEngine(session)
            await engine.credit_asset(user_id=user_id, asset="ORT", amount=15)
            await session.commit()

            frame1 = ws.receive_json()
            assert frame1["type"] == "wallet.updated"
            assert frame1["asset"] == "ORT"
            assert frame1["balance"] == 15
            assert frame1["amount"] == 15
            assert frame1["entry_type"] == "credit"

            await engine.debit_asset(user_id=user_id, asset="ORT", amount=5)
            await session.commit()

            frame2 = ws.receive_json()
            assert frame2["type"] == "wallet.updated"
            assert frame2["asset"] == "ORT"
            assert frame2["balance"] == 10
            assert frame2["amount"] == 5
            assert frame2["entry_type"] == "debit"


async def test_ws_receives_wallet_update_on_internal_transfer(client):
    # Sender
    token_a, user_a = await _register_and_token(client, "ws_transfer_a@ex.com", "student")
    # Add initial balance for sender
    await client.post("/api/v1/auth/logout")

    # Admin to adjust sender balance
    _, admin = await _register_and_token(client, "ws_admin@ex.com", "admin")
    adj = await client.post(
        "/api/v1/admin/rewards/adjust",
        json={
            "user_id": str(user_a["id"]),
            "amount": 100,
            "idempotency_key": "test-adj-123",
            "reason": "Test deposit",
        },
    )
    assert adj.status_code == 200, adj.text
    await client.post("/api/v1/auth/logout")

    # Receiver
    token_b, user_b = await _register_and_token(client, "ws_transfer_b@ex.com", "student")

    # Switch client session to user A
    login_a = await client.post(
        "/api/v1/auth/login", json={"email": "ws_transfer_a@ex.com", "password": "Password123!"}
    )
    assert login_a.status_code == 200, login_a.text
    token_a = client.cookies.get("qloot_session")

    with _ws_client() as tc:
        with (
            tc.websocket_connect(f"/api/v1/ws/notifications?token={token_a}") as ws_a,
            tc.websocket_connect(f"/api/v1/ws/notifications?token={token_b}") as ws_b,
        ):
            # Transfer 40 OPT from A to B
            t_res = await client.post(
                "/api/v1/wallet/transfers",
                json={"to_user_id": str(user_b["id"]), "amount": 40, "note": "Realtime gift"},
            )
            assert t_res.status_code == 200, t_res.text

            # Sender A gets debit
            frame_a = ws_a.receive_json()
            assert frame_a["type"] == "wallet.updated"
            assert frame_a["asset"] == "OPT"
            assert frame_a["balance"] == 60
            assert frame_a["amount"] == 40
            assert frame_a["entry_type"] == "debit"
            assert frame_a["reference_type"] == "transfer_out"

            # Receiver B gets credit
            frame_b = ws_b.receive_json()
            assert frame_b["type"] == "wallet.updated"
            assert frame_b["asset"] == "OPT"
            assert frame_b["balance"] == 40
            assert frame_b["amount"] == 40
            assert frame_b["entry_type"] == "credit"
            assert frame_b["reference_type"] == "transfer_in"
