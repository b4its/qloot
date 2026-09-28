# Matriks Fitur dan Journey

## 1. Matriks Role

| Domain | Student | Teacher | Admin | State utama |
|---|---|---|---|---|
| Identity | register/login/profile/session | profile/session | create role/activate | unauth, active, locked, inactive |
| Learning | course, lesson, material, progress | author/publish/reorder/upload | audit | draft, published, completed |
| AI | summary, grounded Q&A | generate/review questions | config/usage | queued, running, done, failed/refunded |
| Exam | discover, attempt, autosave, result | author, publish, grade, analytics | audit | upcoming, open, in-progress, grading, graded, closed |
| Gamification | quest/task/room/XP/badge | campaign/host/finalize | leaderboard control | draft, open, locked, finalized |
| Wallet | balance, ledger, swap, transfer, withdrawal | reward preview | review/reconcile/chain ops | requested, approved, submitted, confirmed, failed |
| Career | grade/personality/roadmap/consult | counselor/manage resources | governance | draft, in-review, approved, completed |
| Community | post/comment/follow/report | participate | moderate | visible, reported, hidden, resolved |

## 2. Journey J1: Teacher Membuat Learning Campaign

### Flow

1. Teacher membuat course dan target kelas.
2. Menambah lesson, prerequisite, dan expected outcome.
3. Upload PDF; sistem menampilkan extraction quality dan quarantine status.
4. Teacher meminta AI generate questions; biaya/kebijakan ORT terlihat sebelum submit.
5. Teacher review/approve/reject/edit draft.
6. Membuat exam dari question bank, menetapkan policy attempt/shuffle/grace.
7. Menghubungkan exam ke quest, rank reward, budget, dan jendela waktu.
8. Preview sebagai student.
9. Publish campaign.

### Acceptance

- Draft tersimpan tanpa publish.
- Tidak dapat publish bila material unsafe, question pending, reward di atas cap, atau jendela
  waktu invalid.
- Preview tidak menulis progress/reward.
- Semua mutation object-level scoped ke owner/admin.
- Publish menghasilkan notification untuk kelas target.

## 3. Journey J2: Student Menyelesaikan Mission

### Flow

1. Dashboard menunjukkan satu “Lanjutkan” utama dan deadline terdekat.
2. Student membaca material; progress parsial tersimpan.
3. Summary/Q&A mengambil source excerpt dan menunjukkan cost/free quota.
4. Student menjalankan checkpoint/exam dengan server timer dan autosave.
5. Result menunjukkan mastery, feedback, review salah, dan next lesson.
6. Quest eligibility diverifikasi dari attempt, bukan tombol claim.
7. Reward allocation muncul sebagai pending, kemudian confirmed.
8. XP/level/badge/certificate diperbarui idempoten.

### Acceptance

- Refresh/resume tidak kehilangan progress atau answer.
- Submit ganda tidak menggandakan grade/reward.
- Expired attempt auto-submit sesuai policy.
- Failure AI tidak menahan result objektif; status grading dan retry jelas.
- Reward belum confirmed tidak disebut final on-chain.

## 4. Journey J3: Teacher Memantau dan Mengintervensi

### Flow

1. Dashboard menunjukkan queue: question review, grading failed, flagged attempt, low mastery.
2. Teacher membuka cohort analytics dan filter class/course/exam/status.
3. Melihat attempt detail, telemetry dengan disclaimer, similarity, dan feedback.
4. Regrade atau manual override dengan reason.
5. Mengirim follow-up material/task atau konsultasi.
6. Audit trail merekam perubahan dan koreksi reward bila relevan.

### Acceptance

- Override menghitung ulang total/pass dan koreksi reward idempoten.
- Flag tidak otomatis menghukum student.
- Export CSV sesuai filter dan aman dari formula injection.
- Teacher tidak bisa melihat class/object di luar scope.

## 5. Journey J4: Room Kompetitif

### Flow

1. Host membuat room, kapasitas, visibility, dan invite.
2. Student join dengan code/invite.
3. Presence realtime, reconnect, dan resync bila event drop.
4. Host lock room, mulai ronde, publish prompt, reveal result.
5. Leaderboard update dan final event terpersist.
6. Reward hanya dari event terverifikasi.

### Acceptance

- Auth/revoked session menutup socket.
- Multi-tab presence dihitung benar.
- Queue overflow memberi `resync`, bukan stale UI diam-diam.
- Chat/moderation/persisted event memiliki rate/length limit.

## 6. Journey J5: Wallet dan Withdrawal

### Flow

1. Wallet menjelaskan balance available/pending dan asset OPT/QTC/ORT.
2. Student melihat ledger source, reference, dan settlement state.
3. Swap menampilkan rate, receive preview, fee, dan balance requirement.
4. Withdrawal menampilkan destination, amount, fee, review policy, network.
5. Admin approve/reject dengan reason.
6. Worker mengirim aset ke destination; indexer menunggu confirmation.
7. UI menampilkan explorer dan final state; failure direfund sesuai policy.

### Acceptance

- Destination benar-benar menerima aset pada local-chain test.
- Signer/treasury/role invariant diperiksa sebelum submit.
- Request retry tidak menggandakan debit/transfer.
- Cancel hanya pada state yang diizinkan.
- Tidak ada PII/raw key di log atau explorer metadata.

## 7. Journey J6: Certificate dan Verifikasi

### Flow

1. Course completion menerbitkan certificate off-chain.
2. Student memilih/menjalankan anchoring sesuai QTC policy.
3. Outbox/worker menyimpan hash saja di chain.
4. Public verifier menampilkan valid/revoked, holder display name, course, issuer, anchor.

### Acceptance

- Credential ID tidak bisa ditebak secara berbahaya.
- Revoked certificate tidak dapat render sebagai valid.
- Anchoring idempoten dan private data tidak masuk chain.

## 8. Journey J7: Career Human-in-the-loop

### Flow

1. Student mengelola grade dan personality test.
2. Recommendation menjelaskan faktor academic/personality, source, dan confidence.
3. Student submit review; counselor approve/reject dengan notes.
4. Roadmap aktif memiliki task yang benar-benar bisa ditoggle/reorder.
5. Consultation thread dan resource follow-up terhubung.

### Acceptance

- AI/rule output bukan keputusan final tanpa counselor.
- Student dapat memahami alasan recommendation.
- Counselor scope dan audit trail lengkap.

## 9. Journey J8: Admin Economy dan Trust

### Flow

1. Dashboard health: API/DB/Redis/storage/workers/RPC.
2. Economy: issuance, burn, pending liability, treasury coverage, failed tx.
3. Action queue: withdrawal, negative/drift ledger, moderation report, chain failure.
4. Admin resolve dengan reason dan audit request ID.

### Acceptance

- Secret/config sensitive tidak pernah dirender.
- Every critical action confirmed and audited.
- Economy metric dapat direkonsiliasi ke ledger dan chain.

## 10. Cross-Cutting UI States

Setiap route data-driven wajib mendefinisikan:

- `loading`: skeleton, tidak ada false zero.
- `success-empty`: belum ada data + action yang masuk akal.
- `filtered-empty`: reset filter.
- `partial`: section gagal tetapi section lain tetap usable.
- `error`: message, retry, request context bila tersedia.
- `offline/reconnecting`: khusus room/notification.
- `busy`: mutasi disabled, duplicate action dicegah.
- `confirmed`: hanya setelah source of truth menyatakan sukses.
