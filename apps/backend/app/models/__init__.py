"""Import all models so SQLAlchemy metadata is fully populated (Alembic)."""

from app.db.base import Base
from app.models.exam import (
    BP_SCALE,
    Exam,
    ExamAttempt,
    GradingJob,
    GradingResult,
    Question,
    QuestionOption,
    StudentAnswer,
)
from app.models.identity import (
    AuditLog,
    PasswordResetToken,
    Role,
    Session,
    User,
    UserRole,
)
from app.models.learning import (
    Course,
    CourseMember,
    LearningMaterial,
    Lesson,
    LessonProgress,
)
from app.models.quest import (
    Quest,
    QuestAttempt,
    QuestRule,
    QuestWinner,
    Task,
    TaskCompletion,
)
from app.models.ranking import Leaderboard, LeaderboardEntry, RankingSnapshot
from app.models.room import Room, RoomEvent, RoomInvitation, RoomMember
from app.models.social import Badge, Notification, UserBadge
from app.models.wallet import (
    BlockchainEvent,
    BlockchainTransaction,
    ContractDeployment,
    RewardAllocation,
    TransactionOutbox,
    WalletAccount,
    WalletLedgerEntry,
    WithdrawalRequest,
)

__all__ = [
    "Base",
    "BP_SCALE",
    "User",
    "Role",
    "UserRole",
    "Session",
    "PasswordResetToken",
    "AuditLog",
    "Course",
    "CourseMember",
    "Lesson",
    "LearningMaterial",
    "LessonProgress",
    "Room",
    "RoomMember",
    "RoomEvent",
    "RoomInvitation",
    "Exam",
    "Question",
    "QuestionOption",
    "ExamAttempt",
    "StudentAnswer",
    "GradingJob",
    "GradingResult",
    "Quest",
    "QuestRule",
    "QuestAttempt",
    "QuestWinner",
    "Task",
    "TaskCompletion",
    "Leaderboard",
    "LeaderboardEntry",
    "RankingSnapshot",
    "Notification",
    "Badge",
    "UserBadge",
    "WalletAccount",
    "WalletLedgerEntry",
    "RewardAllocation",
    "BlockchainTransaction",
    "BlockchainEvent",
    "ContractDeployment",
    "WithdrawalRequest",
    "TransactionOutbox",
]
