"""Reward/notification/badge side-effects for a quest finalize.

Shared between the HTTP ``POST /quests/{id}/finalize`` endpoint (teacher-
triggered) and the auto-finalize worker sweep (``workers/main.py``), so a
quest that closes on its own gets exactly the same rewards, notifications,
and badges as one a teacher finalizes by hand.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.identity import User
from app.models.quest import Quest, QuestAttempt, QuestWinner
from app.services.quest_service import QuestService
from app.services.realtime import event_bus, room_channel
from app.services.reward_engine import RewardEngine
from app.services.social_service import BadgeService, NotificationService


async def apply_finalize_side_effects(
    session: AsyncSession,
    quest: Quest,
    winners: list[QuestWinner],
    *,
    already_finalized: bool,
) -> int:
    """Allocate rewards and (on the first finalize only) send notifications
    and award badges. Returns the number of reward allocations created.

    Idempotent: a re-finalize (``already_finalized=True``) still allocates
    (allocation itself is idempotent via ``reward_key``) but skips
    notifications/badges so they are never duplicated.
    """
    service = QuestService(session)
    rules = {r.rank: r for r in await service.list_rules(quest.id)}
    engine = RewardEngine(session)
    badges = BadgeService(session)
    notifications = NotificationService(session)

    created = 0
    for w in winners:
        rule = rules.get(w.rank)
        amount = rule.reward_amount if rule else 0
        user_row = await session.get(User, w.user_id)
        if user_row is None or amount <= 0 or w.rank > quest.top_n_winners:
            continue
        await engine.allocate_quest_reward(
            quest=quest, user=user_row, rank=w.rank, amount=amount, score_bp=w.score_bp
        )
        created += 1
        if already_finalized:
            continue
        await notifications.notify(
            user_id=user_row.id,
            kind="reward",
            title=f"You earned {amount} OPT!",
            body=f"Quest '{quest.title}' — rank {w.rank}",
            data={"quest_id": str(quest.id), "rank": w.rank, "amount": amount},
        )
        await badges.award(user=user_row, code="first_reward")
        if w.rank <= 3:
            await badges.award(
                user=user_row, code="top_3", meta={"quest_id": str(quest.id), "rank": w.rank}
            )

    if not already_finalized:
        winner_ids = {w.user_id for w in winners}
        participant_ids = (
            set(
                (
                    await session.execute(
                        select(QuestAttempt.user_id).where(QuestAttempt.quest_id == quest.id)
                    )
                )
                .scalars()
                .all()
            )
            - winner_ids
        )
        await notifications.notify_many(
            user_ids=list(participant_ids),
            kind="quest",
            title=f"Quest '{quest.title}' selesai",
            body="Terima kasih sudah berpartisipasi — cek papan peringkat untuk hasilnya.",
            data={"quest_id": str(quest.id)},
        )

    if quest.room_id is not None:
        await event_bus.publish(
            room_channel(str(quest.room_id)),
            {"type": "quest.finalized", "quest_id": str(quest.id), "winners": len(winners)},
        )

    # Snapshot the quest's final winner standings (survives later edits).
    from app.services.leaderboard_service import LeaderboardService

    await LeaderboardService(session).materialize_quest(quest.id)
    return created


async def finalize_quest_system(session: AsyncSession, quest_id: uuid.UUID) -> int:
    """Finalize one quest with no owning user (worker context) and apply the
    same side-effects the HTTP endpoint applies. Returns allocations created.
    """
    service = QuestService(session)
    already_finalized = (await service.get(quest_id)).status == "finalized"
    quest, winners = await service.finalize_system(quest_id)
    return await apply_finalize_side_effects(
        session, quest, winners, already_finalized=already_finalized
    )
