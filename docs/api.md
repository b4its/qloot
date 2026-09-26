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
POST   /auth/change-password          (in-session; requires current password)
POST   /auth/logout-all               (revoke every session)
PATCH  /auth/profile                  (full_name)
POST   /auth/profile/avatar           (image upload)
GET    /auth/avatars/{user_id}
POST   /auth/change-email/request     (returns the token outside production)
POST   /auth/change-email/confirm
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

Students see **only published** lessons; a draft lesson (`is_published=false`) is
hidden from the lesson list and 404s on direct fetch (owner/admin can still see
it). `PATCH /courses/{id}` honours an explicit `null` to clear a field.

## Materials & AI

```
POST /materials/upload
GET  /materials/{material_id}
GET  /materials/{material_id}/download                  (streams the stored PDF)
POST /materials/{material_id}/generate-questions        (async job)
POST /materials/{material_id}/generate-questions-sync   (dev)
GET  /materials/{material_id}/questions                 (teacher: draft AI questions)
GET  /ai/jobs/{job_id}
POST /ai/questions/{question_id}/regenerate
POST /ai/grade
```

AI-generated questions are created `review_status="pending"`; a teacher approves
or rejects them via `PATCH /questions/{question_id}` (`review_status`) and can
list a material's *pending* drafts via `GET /materials/{material_id}/questions`
(approved questions drop out of that list). An exam cannot be published while it
still contains a question that is not `approved`.

`AI_PROVIDER=openai|gemini` requires the matching API key: if it is missing the
app fails fast rather than silently falling back to the deterministic mock (which
would fabricate grades). `MockProvider` is used only when `AI_PROVIDER=mock`.

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
GET    /rooms/{room_id}/participants     # members + display_name (visibility-guarded)
WS     /ws/rooms/{room_id}                # private rooms: owner/members/admin only
```

Private rooms (`is_public=false`) are only readable by their owner, members and
admins — everyone else gets `404` (existence is never leaked). Participant and
live-leaderboard rows include a `display_name` so the UI never shows a bare UUID.

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
GET /rankings/global?period=all|weekly|monthly
GET /rankings/rooms/{room_id}
GET /rankings/quests/{quest_id}
GET /rankings/me?period=all|weekly|monthly
GET /rankings/leaderboards                          # list materialized snapshots
GET /rankings/leaderboards/{leaderboard_id}/entries  # read one snapshot
POST /rankings/leaderboards/refresh?scope=global|room|quest[&scope_id=...]  # admin

GET /gamification/me                                # caller's XP, level, next-level progress
GET /gamification/levels                            # public level & XP rankings
GET /gamification/levels/{user_id}                  # public user level & activity breakdown card
```

All boards exclude flagged (disqualified) attempts and inactive users, and
`/rankings/me`'s `rank` matches the caller's position in `/rankings/global`
for the same `period` (same `score desc, opc desc, id asc` ordering). XP/levels
use the same best-per-exam, non-flagged aggregation, so the level board agrees
with the score board (<code>/gamification/me</code>, <code>/gamification/levels</code>).
`period=weekly`/`monthly` scope exam totals to the last 7/30 days (platform
timezone); `all` (default) is lifetime. Room/quest leaderboards are also
auto-materialized on room close / quest finalize (`/admin/leaderboards`).

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
POST  /admin/rewards/adjust           (audited manual OPT adjustment)
GET   /admin/withdrawals              (review queue; ?status_filter=)
POST  /admin/withdrawals/{id}/approve
POST  /admin/withdrawals/{id}/reject
GET   /admin/ledger/negative          (accounts in debt)
POST  /admin/ledger/reconcile         (drift sweep)
POST  /admin/blockchain/pause
POST  /admin/blockchain/unpause
GET   /admin/audit-logs               (?action= filter; X-Total-Count)
GET   /admin/config
POST  /admin/notifications            (broadcast system notification to all users)
```

Community moderation (`/community`, role `admin`):

```
GET   /community/reports              (?status_filter=)
POST  /community/reports/{id}/moderate  (hide|delete|dismiss)
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

GET    /users/{user_id}/follow        (follow status + counts)
POST   /users/{user_id}/follow
DELETE /users/{user_id}/follow
GET    /me/following
```

Every catalogued badge is earnable: the 7 curated gameplay badges plus XP
milestones (`xp_500` … `xp_25000`) awarded automatically by
`GET /gamification/me`.

## Certificates

```
GET  /certificates
POST /certificates/sync
GET  /certificates/verify/{credential_id}          (public; name is masked)
GET  /certificates/{credential_id}/render          (official printable HTML document)
POST /certificates/{credential_id}/revoke          (admin)
```

Issuance is automatic when a student completes every published lesson of a
course; the learner is notified. Verify is public and masks the recipient
surname ("Budi Santoso" → "Budi S."); a revoked credential reports
`valid=false` and drops out of the owner's listing.

## Community (social feed)

```
GET    /community/posts                 (?topic=&sort=new|hot|top&following=&limit=&offset=)
POST   /community/posts
GET    /community/posts/{post_id}
DELETE /community/posts/{post_id}       (author/admin)
POST   /community/posts/{post_id}/like
GET    /community/posts/{post_id}/comments
POST   /community/posts/{post_id}/comments
DELETE /community/comments/{comment_id} (author/admin)
PATCH  /community/comments/{comment_id} (author/admin: edit, stamps edited_at)
POST   /community/reports                 (one report per user per object)
GET    /community/reports                 (admin moderation queue)
POST   /community/reports/{report_id}/moderate   (admin: hide|delete|dismiss)
GET    /community/topics
GET    /community/stats
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
GET   /career/grades/export.csv       # download academic transcript CSV
PUT   /career/grades/{grade_id}       # edit one of your own grades
DELETE /career/grades/{grade_id}      # remove one of your own grades

GET   /career/personality
POST  /career/personality

GET   /career/recommendations
POST  /career/recommendations/generate
POST  /career/recommendations/submit
POST  /career/recommendations/approve     (?user_id=student; teacher/admin)
GET   /career/recommendations/pending     (teacher/admin: students awaiting review)

GET   /career/roadmap
PATCH /career/roadmap/{milestone_id}
POST  /career/roadmap
POST  /career/roadmap/reorder
POST  /career/roadmap/{milestone_id}/tasks/{task_index}/toggle
DELETE /career/roadmap/{milestone_id}

GET   /career/counselors
GET   /career/consultations
POST  /career/consultations
POST  /career/consultations/{consultation_id}/cancel
GET   /career/consultations/managed                 (teacher: assigned/open requests)
POST  /career/consultations/{consultation_id}/accept     (teacher)
POST  /career/consultations/{consultation_id}/complete   (teacher)
POST  /career/consultations/{consultation_id}/reschedule (teacher)
GET   /career/consultations/{consultation_id}/messages
POST  /career/consultations/{consultation_id}/messages

GET   /career/resources            (?category=…&q=…&major=…)
POST  /career/resources            (teacher/admin)
PATCH /career/resources/{code}     (teacher/admin)
DELETE /career/resources/{code}    (teacher/admin)
POST  /career/assistant            (body may carry conversation_id to continue)
POST  /career/assistant/stream     (Server-Sent Events; JSON endpoint is the fallback)
GET   /career/assistant/conversations
GET   /career/assistant/conversations/{conversation_id}
DELETE /career/assistant/conversations/{conversation_id}
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
GET    /exams/{exam_id}/results/review      # teacher: per-student answers + correctness

POST   /exams/{exam_id}/questions          # qtype=essay|multiple_choice (+ options[] for MC)
POST   /exams/{exam_id}/questions/reorder  # atomic question reordering
PATCH  /questions/{question_id}            # replace MC options atomically
DELETE /questions/{question_id}

POST /exams/{exam_id}/attempts
PUT  /attempts/{attempt_id}/answers/{question_id}   # answer_text = option label for MC
POST /attempts/{attempt_id}/submit                  # MC graded instantly; essays via AI worker
POST /attempts/{attempt_id}/regrade                 # teacher: re-queue a grading_failed attempt
GET  /attempts/{attempt_id}/result                  # includes exam + (when graded) the answer key
```

Multiple-choice options are `[{text, is_correct}]` (2–8, exactly one correct); the
correct option is never exposed to students taking the exam.

A failed on-chain step is compensated: `reward` and `withdrawal` reverse their
ledger effect, and `swap` / `ai_request` refund the debited OPT / ORT so a user
never loses funds to a failed chain transaction. Outbox rows with an unknown
topic are marked `failed` by the worker (never silently stuck `pending`).

`GET /exams/{exam_id}/results/review` powers the teacher "Hasil peserta" view: for every
student who attempted the exam it returns their name/score plus, per question, the prompt,
the student's answer (option text for MC), whether it was correct, and the score — so a
teacher can see exactly which questions each student got right or wrong.

## Conventions

- Scores use **integer basis points** (`10000 = 100.00%`).
- Errors: `{ "error": { "code", "message", "detail" } }`.
- Every response carries `X-Request-ID`.
- Object-level authorization: owners (or admins) only, never by id alone.
- Read visibility mirrors the list endpoints: a draft quest, a private room and
  their dependent views (winners, rankings, participants, live, events) `404`
  for users who are not the owner/member/admin — existence is never leaked.
