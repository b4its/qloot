"""Community (social feed) service — simulated discussion feed."""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime

from sqlalchemy import Float as SAFloat
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.community import (
    CommunityComment,
    CommunityLike,
    CommunityPost,
    CommunityReport,
)
from app.models.identity import User

log = get_logger("community")

# Topic catalog used for filtering + the "rooms" sidebar.
TOPICS: tuple[str, ...] = (
    "Umum",
    "Desain & UX",
    "Data & AI",
    "Web3 & Blockchain",
    "Karier & Portofolio",
    "Tanya Jawab",
)

# COMM-02: maximum nesting depth for comment replies.
MAX_COMMENT_DEPTH = 3

# COMM-04: cap on @mention notifications per post/comment (anti-spam).
MAX_MENTIONS_PER_POST = 10

# Matches "@Name With Spaces" up to a punctuation/newline boundary. Names are
# matched against users.full_name case-insensitively by the caller.
_MENTION_RE = re.compile(r"@([A-Za-z0-9_.\- ]{2,64}?)(?=[,.!?;:\n]|$)")


def _extract_mentions(body: str) -> list[str]:
    """Return the distinct @mention names (trimmed, order preserved)."""
    seen: list[str] = []
    for m in _MENTION_RE.finditer(body or ""):
        name = m.group(1).strip()
        if name and name not in seen:
            seen.append(name)
    return seen


class CommunityService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_posts(
        self,
        *,
        viewer_id: uuid.UUID | None,
        topic: str | None = None,
        sort: str = "new",
        following_only: bool = False,
        limit: int = 30,
        offset: int = 0,
        include_hidden_for: uuid.UUID | None = None,
    ) -> list[dict]:
        stmt = select(CommunityPost)
        # COMM-01: hidden posts disappear from the feed but stay visible to
        # their own author (include_hidden_for) and to admins.
        if include_hidden_for is not None:
            stmt = stmt.where(
                (CommunityPost.hidden.is_(False))
                | (CommunityPost.author_id == include_hidden_for)
            )
        else:
            stmt = stmt.where(CommunityPost.hidden.is_(False))
        if topic:
            stmt = stmt.where(CommunityPost.topic == topic)
        if following_only and viewer_id is not None:
            # COMM-06: show only posts by people the viewer follows (plus own).
            from app.services.social_service import FollowService

            ids = await FollowService(self.session).following_ids(viewer_id)
            ids = [*ids, viewer_id]
            stmt = stmt.where(CommunityPost.author_id.in_(ids))

        engaged = CommunityPost.like_count * 2 + CommunityPost.comment_count
        if sort == "top":
            # Highest engagement first (deterministic tie-break by recency).
            stmt = stmt.order_by(engaged.desc(), CommunityPost.created_at.desc())
        elif sort == "hot":
            # Engagement with deterministic time decay: age in hours (min 1).
            age_hours = func.greatest(
                func.extract("epoch", func.now() - CommunityPost.created_at) / 3600.0,
                1.0,
            )
            hot = func.cast(engaged, SAFloat) / age_hours
            stmt = stmt.order_by(hot.desc(), CommunityPost.created_at.desc())
        else:
            stmt = stmt.order_by(CommunityPost.created_at.desc())

        stmt = stmt.limit(limit).offset(offset)
        posts = list((await self.session.execute(stmt)).scalars().all())
        return await self._decorate(posts, viewer_id)

    async def get_post(
        self, post_id: uuid.UUID, viewer_id: uuid.UUID | None
    ) -> dict:
        post = await self.session.get(CommunityPost, post_id)
        if post is None:
            raise NotFoundError("Post not found")
        decorated = (await self._decorate([post], viewer_id))[0]
        include_hidden_for = viewer_id if viewer_id == post.author_id else None
        comments = await self.list_comments(
            post_id, include_hidden_for=include_hidden_for
        )
        decorated["comments"] = comments
        return decorated

    async def list_comments(
        self,
        post_id: uuid.UUID,
        *,
        limit: int = 100,
        offset: int = 0,
        include_hidden_for: uuid.UUID | None = None,
    ) -> list[dict]:
        stmt = (
            select(CommunityComment, User.full_name)
            .join(User, User.id == CommunityComment.author_id)
            .where(CommunityComment.post_id == post_id)
        )
        if include_hidden_for is not None:
            stmt = stmt.where(
                (CommunityComment.hidden.is_(False))
                | (CommunityComment.author_id == include_hidden_for)
            )
        else:
            stmt = stmt.where(CommunityComment.hidden.is_(False))
        stmt = stmt.order_by(CommunityComment.created_at).limit(limit).offset(offset)
        rows = (await self.session.execute(stmt)).all()
        return [
            {
                "id": c.id,
                "author_id": c.author_id,
                "author_name": name,
                "body": c.body,
                "parent_id": c.parent_id,
                "hidden": c.hidden,
                "edited_at": c.edited_at,
                "created_at": c.created_at,
            }
            for c, name in rows
        ]

    async def create_post(self, user: User, *, body: str, topic: str) -> CommunityPost:
        post = CommunityPost(author_id=user.id, body=body, topic=topic or "Umum")
        self.session.add(post)
        await self.session.flush()
        log.info("community_post_created", post=str(post.id), user=str(user.id))
        # COMM-04: notify @mentioned users.
        await self._notify_mentions(user, body, post_id=post.id)
        return post

    async def add_comment(
        self,
        user: User,
        post_id: uuid.UUID,
        *,
        body: str,
        parent_id: uuid.UUID | None = None,
    ) -> CommunityComment:
        post = await self.session.get(CommunityPost, post_id)
        if post is None:
            raise NotFoundError("Post not found")
        # COMM-02: nested replies, but bounded depth so threads stay readable.
        if parent_id is not None:
            parent = await self.session.get(CommunityComment, parent_id)
            if parent is None or parent.post_id != post_id:
                raise NotFoundError("Parent comment not found")
            # Depth of the *new* comment = 1 (this comment) + its ancestors.
            depth = 2
            cursor: CommunityComment | None = parent
            while cursor is not None and cursor.parent_id is not None:
                depth += 1
                if depth > MAX_COMMENT_DEPTH:
                    break
                cursor = await self.session.get(CommunityComment, cursor.parent_id)
            if depth > MAX_COMMENT_DEPTH:
                raise ValidationError(f"Balasan maksimum {MAX_COMMENT_DEPTH} tingkat")
        comment = CommunityComment(
            post_id=post_id, author_id=user.id, body=body, parent_id=parent_id
        )
        self.session.add(comment)
        post.comment_count = (post.comment_count or 0) + 1
        await self.session.flush()
        # COMM-03: notify the post author (never yourself); the notification
        # service honours the author's per-kind preference (C54).
        if post.author_id != user.id:
            from app.services.social_service import NotificationService

            await NotificationService(self.session).notify(
                user_id=post.author_id,
                kind="community",
                title=f"{user.full_name} mengomentari pos Anda",
                body=body[:140],
                data={"post_id": str(post_id), "comment_id": str(comment.id)},
            )
        # COMM-04: notify @mentioned users (bounded, never the author).
        await self._notify_mentions(user, body, post_id=post_id, comment_id=comment.id)
        return comment

    async def edit_comment(
        self, user: User, comment_id: uuid.UUID, *, body: str
    ) -> CommunityComment:
        """Author edits their own comment; marks it edited (COMM-02)."""
        comment = await self.session.get(CommunityComment, comment_id)
        if comment is None:
            raise NotFoundError("Comment not found")
        if not user.has_role("admin") and comment.author_id != user.id:
            raise ForbiddenError("You can only edit your own comments")
        comment.body = body
        comment.edited_at = datetime.now(UTC)
        await self.session.flush()
        return comment

    async def toggle_like(self, user: User, post_id: uuid.UUID) -> tuple[CommunityPost, bool]:
        post = await self.session.get(CommunityPost, post_id)
        if post is None:
            raise NotFoundError("Post not found")
        existing = (
            await self.session.execute(
                select(CommunityLike).where(
                    CommunityLike.post_id == post_id, CommunityLike.user_id == user.id
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            await self.session.delete(existing)
            post.like_count = max(0, (post.like_count or 0) - 1)
            liked = False
        else:
            self.session.add(CommunityLike(post_id=post_id, user_id=user.id))
            post.like_count = (post.like_count or 0) + 1
            liked = True
            # COMM-03: notify the author (never yourself). Unlike/Unlike does
            # not notify; dedup is inherent (one like per user per post).
            if post.author_id != user.id:
                from app.services.social_service import NotificationService

                await NotificationService(self.session).notify(
                    user_id=post.author_id,
                    kind="community",
                    title=f"{user.full_name} menyukai pos Anda",
                    body=(post.body or "")[:140],
                    data={"post_id": str(post_id)},
                )
        await self.session.flush()
        return post, liked

    async def delete_post(self, user: User, post_id: uuid.UUID) -> None:
        post = await self.session.get(CommunityPost, post_id)
        if post is None:
            raise NotFoundError("Post not found")
        if not user.has_role("admin") and post.author_id != user.id:
            raise ForbiddenError("You can only delete your own posts")
        await self.session.delete(post)

    async def delete_comment(self, user: User, comment_id: uuid.UUID) -> None:
        """Delete a comment (author or admin) and decrement the post's count."""
        comment = await self.session.get(CommunityComment, comment_id)
        if comment is None:
            raise NotFoundError("Comment not found")
        if not user.has_role("admin") and comment.author_id != user.id:
            raise ForbiddenError("You can only delete your own comments")
        post = await self.session.get(CommunityPost, comment.post_id)
        if post is not None:
            post.comment_count = max(0, (post.comment_count or 0) - 1)
        await self.session.delete(comment)

    async def stats(self) -> dict:
        members = int(
            (
                await self.session.execute(
                    select(func.count()).select_from(User).where(User.is_active.is_(True))
                )
            ).scalar_one()
        )
        posts = int(
            (
                await self.session.execute(select(func.count()).select_from(CommunityPost))
            ).scalar_one()
        )
        comments = int(
            (
                await self.session.execute(select(func.count()).select_from(CommunityComment))
            ).scalar_one()
        )
        return {"members": members, "posts": posts, "comments": comments}

    async def topics(self) -> list[dict]:
        rows = (
            await self.session.execute(
                select(CommunityPost.topic, func.count(CommunityPost.id)).group_by(
                    CommunityPost.topic
                )
            )
        ).all()
        counts = {t: int(c) for t, c in rows}
        return [{"name": t, "posts": counts.get(t, 0)} for t in TOPICS]

    # --- helpers -----------------------------------------------------------
    async def _notify_mentions(
        self,
        author: User,
        body: str,
        *,
        post_id: uuid.UUID,
        comment_id: uuid.UUID | None = None,
    ) -> None:
        """Notify users @mentioned in ``body`` (COMM-04).

        Mentions are matched case-insensitively against ``full_name`` and
        capped per content to bound notification spam. Unknown names are left
        as plain text (no notification). The author is never notified.
        """
        names = _extract_mentions(body)
        if not names:
            return
        from app.services.social_service import NotificationService

        notified: set[uuid.UUID] = set()
        for name in names:
            if len(notified) >= MAX_MENTIONS_PER_POST:
                break
            user = (
                await self.session.execute(
                    select(User).where(func.lower(User.full_name) == name.lower())
                )
            ).scalars().first()
            if user is None or user.id == author.id or user.id in notified:
                continue
            notified.add(user.id)
            mention_data = {
                "post_id": str(post_id),
                "comment_id": str(comment_id) if comment_id else None,
            }
            await NotificationService(self.session).notify(
                user_id=user.id,
                kind="community",
                title=f"{author.full_name} menyebut Anda",
                body=body[:140],
                data=mention_data,
            )

    async def _decorate(
        self, posts: list[CommunityPost], viewer_id: uuid.UUID | None
    ) -> list[dict]:
        if not posts:
            return []
        author_ids = {p.author_id for p in posts}
        authors = {
            u.id: u
            for u in (await self.session.execute(select(User).where(User.id.in_(author_ids))))
            .scalars()
            .all()
        }
        liked: set[uuid.UUID] = set()
        if viewer_id is not None:
            liked = {
                row[0]
                for row in (
                    await self.session.execute(
                        select(CommunityLike.post_id).where(
                            CommunityLike.user_id == viewer_id,
                            CommunityLike.post_id.in_([p.id for p in posts]),
                        )
                    )
                ).all()
            }
        out = []
        for p in posts:
            author = authors.get(p.author_id)
            ref = author.chain_user_ref if author else "0x"
            out.append(
                {
                    "id": p.id,
                    "author_id": p.author_id,
                    "author_name": author.full_name if author else "Pengguna",
                    "handle": f"{ref[:6]}…{ref[-4:]}" if author else "0x0",
                    "topic": p.topic,
                    "body": p.body,
                    "like_count": p.like_count,
                    "comment_count": p.comment_count,
                    "liked_by_me": p.id in liked,
                    "hidden": p.hidden,
                    "created_at": p.created_at,
                }
            )
        return out

    # --- moderation (COMM-01) ---------------------------------------------
    async def report(
        self, user: User, *, target_type: str, target_id: uuid.UUID, reason: str
    ) -> CommunityReport:

        if target_type not in ("post", "comment"):
            raise ValidationError("target_type must be post|comment")
        target: CommunityPost | CommunityComment | None
        if target_type == "post":
            target = await self.session.get(CommunityPost, target_id)
        else:
            target = await self.session.get(CommunityComment, target_id)
        if target is None:
            raise NotFoundError("Target not found")
        existing = (
            await self.session.execute(
                select(CommunityReport).where(
                    CommunityReport.reporter_id == user.id,
                    CommunityReport.target_type == target_type,
                    CommunityReport.target_id == target_id,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            raise ConflictError("You already reported this")
        rep = CommunityReport(
            reporter_id=user.id,
            target_type=target_type,
            target_id=target_id,
            reason=reason[:255],
            status="open",
        )
        self.session.add(rep)
        await self.session.flush()
        return rep

    async def list_reports(
        self, *, status: str | None = None, limit: int = 100, offset: int = 0
    ) -> list[dict]:

        stmt = select(CommunityReport).order_by(CommunityReport.created_at.desc())
        if status:
            stmt = stmt.where(CommunityReport.status == status)
        stmt = stmt.limit(limit).offset(offset)
        reports = list((await self.session.execute(stmt)).scalars().all())
        out = []
        for r in reports:
            body = None
            if r.target_type == "post":
                p = await self.session.get(CommunityPost, r.target_id)
                body = p.body if p else None
            else:
                c = await self.session.get(CommunityComment, r.target_id)
                body = c.body if c else None
            out.append(
                {
                    "id": r.id,
                    "reporter_id": r.reporter_id,
                    "target_type": r.target_type,
                    "target_id": r.target_id,
                    "reason": r.reason,
                    "status": r.status,
                    "body": body,
                    "created_at": r.created_at,
                }
            )
        return out

    async def moderate(
        self, admin: User, report_id: uuid.UUID, action: str
    ) -> CommunityReport:
        """Admin resolves a report: hide | delete | dismiss (COMM-01)."""

        if not admin.has_role("admin"):
            raise ForbiddenError("Admin only")
        report = await self.session.get(CommunityReport, report_id)
        if report is None:
            raise NotFoundError("Report not found")
        if action == "dismiss":
            report.status = "dismissed"
        elif action in ("hide", "delete"):
            if report.target_type == "post":
                post = await self.session.get(CommunityPost, report.target_id)
                if post is not None:
                    if action == "hide":
                        post.hidden = True
                    else:
                        await self.session.delete(post)
            else:
                comment = await self.session.get(CommunityComment, report.target_id)
                if comment is not None:
                    if action == "hide":
                        comment.hidden = True
                    else:
                        await self.session.delete(comment)
            report.status = "actioned"
        else:
            raise ValidationError("action must be hide|delete|dismiss")
        await self.session.flush()
        return report
