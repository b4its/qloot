"""AI usage metering: charge ORT per real AI request, refund on failure.

The README's economy is "1 request = 1 ORT". This service is the single choke
point that turns that claim into behaviour:

  * ``charge_job`` is called in the request context right after an AI job row is
    created (generation or essay grading). It consumes a free-tier slot when the
    user still has one, otherwise it debits 1 ORT. Insufficient balance with no
    free slot raises ``PaymentRequiredError`` (402) — and because it runs in the
    same transaction as job creation, the job is rolled back too.
  * ``refund_job`` is called from the worker when a job reaches a terminal
    failure, returning the ORT so a provider outage never costs the user.

Both are idempotent per job via the ``ai_usage_charges`` row (unique per job),
so worker retries never double-charge or double-refund.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import PaymentRequiredError
from app.core.logging import get_logger
from app.models.identity import User
from app.models.wallet import AiUsageCharge
from app.services.reward_engine import RewardEngine

log = get_logger("ai_usage")


class AiUsageService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _get_charge(self, job_id: uuid.UUID) -> AiUsageCharge | None:
        return (
            await self.session.execute(
                select(AiUsageCharge).where(AiUsageCharge.job_id == job_id)
            )
        ).scalar_one_or_none()

    async def free_requests_remaining(self, user_id: uuid.UUID) -> int:
        """Free-tier AI requests left for a user (never negative)."""
        if settings.ai_free_requests <= 0:
            return 0
        used = (
            await self.session.execute(
                select(func.count())
                .select_from(AiUsageCharge)
                .where(
                    AiUsageCharge.user_id == user_id,
                    AiUsageCharge.charged.is_(False),
                )
            )
        ).scalar_one()
        return max(0, settings.ai_free_requests - int(used))

    async def charge_job(self, *, user: User, job_id: uuid.UUID) -> None:
        """Charge 1 ORT for an AI job, or consume a free-tier slot (idempotent)."""
        existing = await self._get_charge(job_id)
        if existing is not None:
            return  # already metered for this job

        free_remaining = await self.free_requests_remaining(user.id)
        charge = AiUsageCharge(job_id=job_id, user_id=user.id, charged=False)
        if free_remaining <= 0:
            engine = RewardEngine(self.session)
            balance = await engine.asset_balance(user.id, "ORT")
            if balance < 1:
                raise PaymentRequiredError(
                    "Kredit AI (ORT) habis. Tukar OPT menjadi ORT di halaman dompet "
                    "untuk melanjutkan.",
                    detail={"required": 1, "balance": balance},
                )
            await engine.debit_asset(user_id=user.id, asset="ORT", amount=1)
            charge.charged = True

        try:
            async with self.session.begin_nested():
                self.session.add(charge)
                await self.session.flush()
        except IntegrityError:
            # Concurrent charge for the same job won the race; assume it stands.
            return
        log.info(
            "ai_job_metered",
            user_id=str(user.id),
            job_id=str(job_id),
            charged=charge.charged,
        )

    async def refund_job(self, *, user_id: uuid.UUID | None, job_id: uuid.UUID) -> None:
        """Return the ORT charged for a failed job (idempotent, no-op if free)."""
        charge = await self._get_charge(job_id)
        if charge is None or not charge.charged or charge.refunded:
            return
        await RewardEngine(self.session).refund_ai_request(user_id=charge.user_id, requests=1)
        charge.refunded = True
        await self.session.flush()
        log.info("ai_job_refunded", user_id=str(charge.user_id), job_id=str(job_id))
