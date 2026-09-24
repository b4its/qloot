"""Community (social feed) service — simulated discussion feed."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ForbiddenError, NotFoundError
from app.core.logging import get_logger
from app.models.community import CommunityComment, CommunityLike, CommunityPost
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


class CommunityService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_posts(
        self,
        *,
        viewer_id: uuid.UUID | None,
        topic: str | None = None,
        limit: int = 30,
        offset: int = 0,
    ) -> list[dict]:
        stmt = select(CommunityPost).order_by(CommunityPost.created_at.desc())
        if topic:
            stmt = stmt.where(CommunityPost.topic == topic)
        stmt = stmt.limit(limit).offset(offset)
        posts = list((await self.session.execute(stmt)).scalars().all())
        return await self._decorate(posts, viewer_id)

    async def get_post(self, post_id: uuid.UUID, viewer_id: uuid.UUID | None) -> dict:
        post = await self.session.get(CommunityPost, post_id)
        if post is None:
            raise NotFoundError("Post not found")
        decorated = (await self._decorate([post], viewer_id))[0]
        comments = await self.list_comments(post_id)
        decorated["comments"] = comments
        return decorated

    async def list_comments(
        self, post_id: uuid.UUID, *, limit: int = 100, offset: int = 0
    ) -> list[dict]:
        stmt = (
            select(CommunityComment, User.full_name)
            .join(User, User.id == CommunityComment.author_id)
            .where(CommunityComment.post_id == post_id)
            .order_by(CommunityComment.created_at)
            .limit(limit)
            .offset(offset)
        )
        rows = (await self.session.execute(stmt)).all()
        return [
            {
                "id": c.id,
                "author_id": c.author_id,
                "author_name": name,
                "body": c.body,
                "created_at": c.created_at,
            }
            for c, name in rows
        ]

    async def create_post(self, user: User, *, body: str, topic: str) -> CommunityPost:
        post = CommunityPost(author_id=user.id, body=body, topic=topic or "Umum")
        self.session.add(post)
        await self.session.flush()
        log.info("community_post_created", post=str(post.id), user=str(user.id))
        return post

    async def add_comment(self, user: User, post_id: uuid.UUID, *, body: str) -> CommunityComment:
        post = await self.session.get(CommunityPost, post_id)
        if post is None:
            raise NotFoundError("Post not found")
        comment = CommunityComment(post_id=post_id, author_id=user.id, body=body)
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
                    "created_at": p.created_at,
                }
            )
        return out
