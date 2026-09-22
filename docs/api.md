# QLoot API Overview

Base path: `/api/v1` · Interactive docs: `/docs` · OpenAPI: `/api/v1/openapi.json`

Authentication uses an HttpOnly session cookie (`qloot_session`, `SameSite=Lax`).
Send `Authorization: Bearer <token>` for non-browser clients.

## Health & metrics

```
GET  /health/live
GET  /health/ready
GET  /metrics            (Prometheus text)
```

## Auth (`/auth`)

```
POST   /auth/register
POST   /auth/login
POST   /auth/logout
POST   /auth/refresh
POST   /auth/forgot-password
POST   /auth/reset-password
GET    /auth/me
GET    /auth/sessions
DELETE /auth/sessions/{session_id}
```

## Learning

```
GET    /courses
POST   /courses                      (teacher)
GET    /courses/{course_id}
PATCH  /courses/{course_id}          (owner)
DELETE /courses/{course_id}          (owner)
GET    /courses/{course_id}/lessons
POST   /courses/{course_id}/lessons  (owner)
GET    /lessons/{lesson_id}
PATCH  /lessons/{lesson_id}          (owner)
POST   /lessons/{lesson_id}/progress
GET    /me/learning-progress
```

## Materials & AI

```
POST /materials/upload
GET  /materials/{material_id}
POST /materials/{material_id}/generate-questions        (async job)
POST /materials/{material_id}/generate-questions-sync   (dev)
GET  /ai/jobs/{job_id}
POST /ai/questions/{question_id}/regenerate
POST /ai/grade
```

## Rooms

```
GET    /rooms
POST   /rooms                        (teacher)
GET    /rooms/{room_id}
PATCH  /rooms/{room_id}              (owner)
POST   /rooms/{room_id}/join
POST   /rooms/join-by-code
POST   /rooms/{room_id}/leave
POST   /rooms/{room_id}/open         (owner)
POST   /rooms/{room_id}/close        (owner)
GET    /rooms/{room_id}/participants
WS     /ws/rooms/{room_id}
```

## Exams

```
GET    /exams
POST   /exams                        (teacher)
GET    /exams/{exam_id}
PATCH  /exams/{exam_id}              (owner)
POST   /exams/{exam_id}/publish      (owner)
POST   /exams/{exam_id}/close        (owner)
POST   /exams/{exam_id}/questions    (owner)
PATCH  /questions/{question_id}      (owner)
POST   /exams/{exam_id}/attempts
GET    /attempts
GET    /attempts/{attempt_id}
PUT    /attempts/{attempt_id}/answers/{question_id}
POST   /attempts/{attempt_id}/submit
GET    /attempts/{attempt_id}/result
GET    /exams/{exam_id}/results      (owner)
```

## Quests & tasks

```
GET    /quests
POST   /quests                       (teacher)
GET    /quests/{quest_id}
PATCH  /quests/{quest_id}            (owner)
POST   /quests/{quest_id}/publish    (owner)
POST   /quests/{quest_id}/finalize   (owner)
GET    /quests/{quest_id}/winners

GET    /tasks
POST   /tasks                        (teacher)
PATCH  /tasks/{task_id}              (owner)
POST   /tasks/{task_id}/complete
```

## Rankings

```
GET /rankings/global
GET /rankings/rooms/{room_id}
GET /rankings/quests/{quest_id}
GET /rankings/me
```

## Wallet & blockchain

```
GET  /wallet                       # OPT balance (base currency)
PATCH /wallet/address              # set your personal withdrawal wallet
GET  /wallet/assets                # per-asset balances (OPT/QTC/ORT)
POST /wallet/swap                  # convert OPT -> QTC/ORT via OryphemProxy (ORX)
POST /wallet/ai-requests           # spend ORT on AI usage (1 request = 1 ORT)
GET  /wallet/ledger
GET  /wallet/rewards
GET  /wallet/reconciliation
POST /wallet/transfers
POST /wallet/withdrawals
GET  /wallet/withdrawals/{withdrawal_id}

GET  /blockchain/status            # address-free chain status
GET  /blockchain/contract          # admin: configured assets + deployments
GET  /blockchain/transactions
GET  /blockchain/transactions/{tx_hash}
GET  /blockchain/events
GET  /blockchain/allocations
```

Admin-only extra: `GET /blockchain/status/admin` (asset addresses + treasury) and
`POST /admin/blockchain/pause|unpause?asset=OPT|QTC|ORT`.

## Admin (`/admin`, role `admin`)

```
GET   /admin/users
PATCH /admin/users/{user_id}/role
GET   /admin/rewards
POST  /admin/rewards/{reward_id}/retry
POST  /admin/rewards/{reward_id}/cancel
POST  /admin/blockchain/pause
POST  /admin/blockchain/unpause
GET   /admin/audit-logs
GET   /admin/config
```

## Notifications & badges

```
GET  /notifications
GET  /notifications/unread-count
POST /notifications/{notification_id}/read
POST /notifications/read-all
POST /admin/notifications            (admin broadcast)

GET  /badges
GET  /me/badges
```

## Teacher

```
GET  /teacher/submissions
GET  /teacher/analytics
```

## Career guidance (simulated)

```
GET   /career/dashboard
GET   /career/grades
POST  /career/grades

GET   /career/personality
POST  /career/personality

GET   /career/recommendations
POST  /career/recommendations/generate
POST  /career/recommendations/submit
POST  /career/recommendations/approve

GET   /career/roadmap
PATCH /career/roadmap/{milestone_id}

GET   /career/counselors
GET   /career/consultations
POST  /career/consultations
POST  /career/consultations/{consultation_id}/cancel

GET   /career/resources            (?category=course|extracurricular|material)
POST  /career/assistant
```

## Learning extras

```
GET  /me/subjects
GET  /materials/{material_id}/summary
POST /materials/{material_id}/ask
GET  /rooms/{room_id}/live
GET  /rooms/{room_id}/events
POST /rooms/{room_id}/invite
POST /rooms/invitations/accept
```

## Exams & multiple-choice questions

```
GET    /exams
POST   /exams
GET    /exams/{exam_id}
PATCH  /exams/{exam_id}
POST   /exams/{exam_id}/publish
POST   /exams/{exam_id}/close
DELETE /exams/{exam_id}
GET    /exams/{exam_id}/results            # teacher: attempts + display_name + pagination

POST   /exams/{exam_id}/questions          # qtype=essay|multiple_choice (+ options[] for MC)
PATCH  /questions/{question_id}            # replace MC options atomically
DELETE /questions/{question_id}

POST /exams/{exam_id}/attempts
PUT  /attempts/{attempt_id}/answers/{question_id}   # answer_text = option label for MC
POST /attempts/{attempt_id}/submit                  # MC graded instantly; essays via AI worker
GET  /attempts/{attempt_id}/result                  # includes exam + (when graded) the answer key
```

Multiple-choice options are `[{text, is_correct}]` (2–8, exactly one correct); the
correct option is never exposed to students taking the exam.

## Conventions

- Scores use **integer basis points** (`10000 = 100.00%`).
- Errors: `{ "error": { "code", "message", "detail" } }`.
- Every response carries `X-Request-ID`.
- Object-level authorization: owners (or admins) only, never by id alone.
