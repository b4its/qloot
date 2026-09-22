#!/usr/bin/env bash
# ============================================================================
# QLoot end-to-end scenario (blueprint §24.4)
#
# Exercises the live stack: teacher registers, uploads a PDF, generates
# questions with AI, creates an exam + quest, three students submit, AI grades,
# winners are finalized deterministically, rewards flow through the ledger and
# the blockchain worker, and admin can reconcile.
#
# Requires: `make up` + `make db-migrate` with the stack healthy.
# ============================================================================
set -euo pipefail

API="${API_URL:-http://localhost:8000}/api/v1"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

say() { printf '\n\033[1;34m== %s ==\033[0m\n' "$*"; }
ok()  { printf '  \033[32m✓\033[0m %s\n' "$*"; }

jqget() { python3 -c "import sys,json; d=json.load(sys.stdin); print(d$1)"; }

# --- helpers ---------------------------------------------------------------
register() {
  local jar="$1" email="$2" name="$3" role="$4"
  curl -fsS -c "$jar" -X POST "$API/auth/register" \
    -H 'Content-Type: application/json' \
    -d "{\"email\":\"$email\",\"full_name\":\"$name\",\"password\":\"Password123!\",\"role\":\"$role\"}"
}
login() {
  local jar="$1" email="$2" password="${3:-Password123!}"
  curl -fsS -c "$jar" -X POST "$API/auth/login" \
    -H 'Content-Type: application/json' \
    -d "{\"email\":\"$email\",\"password\":\"$password\"}"
}
api() { local jar="$1"; shift; curl -fsS -b "$jar" "$@"; }

SUF="$(date +%s)"

# ---------------------------------------------------------------------------
say "1. Teacher registers"
TEACHER="$TMP/teacher.jar"
register "$TEACHER" "e2e_teacher_$SUF@example.com" "E2E Teacher" teacher >/dev/null
ok "teacher account created"

say "2. Teacher uploads a PDF material"
PDF="$TMP/material.pdf"
python3 - "$PDF" <<'PY'
import sys
text = "Machine learning is a branch of artificial intelligence. Supervised learning uses labelled data."
stream = b"BT /F1 12 Tf 72 720 Td (" + text.encode() + b") Tj ET"
objs = [
    b"<< /Type /Catalog /Pages 2 0 R >>",
    b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
    b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
]
out = bytearray(b"%PDF-1.4\n"); offs = [0]
for i, o in enumerate(objs, 1):
    offs.append(len(out)); out += b"%d 0 obj\n" % i + o + b"\nendobj\n"
xref = len(out)
out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
for off in offs[1:]:
    out += b"%010d 00000 n \n" % off
out += b"trailer << /Root 1 0 R /Size %d >>\nstartxref\n%d\n%%%%EOF" % (len(objs) + 1, xref)
open(sys.argv[1], "wb").write(out)
PY
MATERIAL=$(api "$TEACHER" -X POST "$API/materials/upload" -F "file=@$PDF;type=application/pdf")
MATERIAL_ID=$(echo "$MATERIAL" | jqget "['id']")
ok "material $MATERIAL_ID uploaded"

say "3. AI generates questions from the material"
GEN=$(api "$TEACHER" -X POST "$API/materials/$MATERIAL_ID/generate-questions-sync" \
  -H 'Content-Type: application/json' -d '{"count":2,"language":"en"}')
NQ=$(echo "$GEN" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))")
ok "$NQ questions generated (pending review)"

say "4. Teacher creates an exam, adds approved questions, publishes"
EXAM=$(api "$TEACHER" -X POST "$API/exams" -H 'Content-Type: application/json' \
  -d '{"title":"E2E AI Exam","duration_minutes":30,"passing_score_bp":5000}')
EXAM_ID=$(echo "$EXAM" | jqget "['id']")

# Attach the AI-generated questions to the exam, capturing the created ids.
: > "$TMP/qids.txt"
echo "$GEN" | python3 -c "
import sys, json
for q in json.load(sys.stdin):
    print(json.dumps({'prompt': q['prompt'], 'correct_answer': q.get('correct_answer') or ''}))
" | while IFS= read -r body; do
  CREATED=$(api "$TEACHER" -X POST "$API/exams/$EXAM_ID/questions" \
    -H 'Content-Type: application/json' -d "$body")
  echo "$CREATED" | jqget "['id']" >> "$TMP/qids.txt"
done
QIDS=$(cat "$TMP/qids.txt")
NQID=$(echo "$QIDS" | grep -c .)
PUB=$(api "$TEACHER" -X POST "$API/exams/$EXAM_ID/publish")
ok "exam published with $NQID questions"

say "5. Teacher creates a quest with 3 reward ranks (100/60/40 OPT)"
QUEST=$(api "$TEACHER" -X POST "$API/quests" -H 'Content-Type: application/json' \
  -d "{\"title\":\"E2E Speed Quest\",\"exam_id\":\"$EXAM_ID\",\"top_n_winners\":3,\"rules\":[{\"rank\":1,\"reward_amount\":100},{\"rank\":2,\"reward_amount\":60},{\"rank\":3,\"reward_amount\":40}]}")
QUEST_ID=$(echo "$QUEST" | jqget "['id']")
api "$TEACHER" -X POST "$API/quests/$QUEST_ID/publish" >/dev/null
ok "quest $QUEST_ID open"

say "6. Three students register and submit answers"
declare -a STUDENT_JARS=()
declare -a ATTEMPT_IDS=()
for i in 1 2 3; do
  JAR="$TMP/student$i.jar"
  register "$JAR" "e2e_student${i}_$SUF@example.com" "E2E Student $i" student >/dev/null
  STUDENT_JARS+=("$JAR")
  ATT=$(api "$JAR" -X POST "$API/exams/$EXAM_ID/attempts")
  ATT_ID=$(echo "$ATT" | jqget "['id']")
  ATTEMPT_IDS+=("$ATT_ID")
  # Answer every question that belongs to this exam.
  echo "$QIDS" | while read -r qid; do
    [ -z "$qid" ] && continue
    api "$JAR" -X PUT "$API/attempts/$ATT_ID/answers/$qid" -H 'Content-Type: application/json' \
      -d '{"answer_text":"Machine learning is a branch of artificial intelligence that uses labelled data."}' >/dev/null
  done
  api "$JAR" -X POST "$API/attempts/$ATT_ID/submit" >/dev/null
  ok "student $i submitted attempt $ATT_ID"
done

say "7. AI worker grades the attempts"
sleep 6
for ATT_ID in "${ATTEMPT_IDS[@]}"; do
  RES=$(api "$TEACHER" "$API/attempts/$ATT_ID/result")
  STATUS=$(echo "$RES" | jqget "['attempt']['status']")
  SCORE=$(echo "$RES" | jqget "['attempt']['score_bp']")
  ok "attempt $ATT_ID status=$STATUS score_bp=$SCORE"
done

say "8. Teacher finalizes the quest -> deterministic winners"
FIN=$(api "$TEACHER" -X POST "$API/quests/$QUEST_ID/finalize")
echo "$FIN" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print('  winners:', len(d['winners']), 'allocations:', d['allocations_created'])
for w in d['winners']:
    print(f\"    rank {w['rank']}: {w['user_id'][:8]}… score_bp={w['score_bp']} reward={w[\"reward_amount\"]} OPT\")
"
ok "winners finalized"

say "9. Blockchain worker processes reward outbox (dry-run chain)"
sleep 8
TXS=$(api "$TEACHER" "$API/blockchain/transactions")
NTX=$(echo "$TXS" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))")
echo "$TXS" | python3 -c "
import sys, json
for t in json.load(sys.stdin)[:5]:
    print(f\"    {t['method']} status={t['status']} tx={str(t['transaction_hash'])[:18]}…\")
"
ok "$NTX blockchain transactions recorded"

say "10. Student wallet reflects the OPT reward + ledger"
WINNER_JAR="${STUDENT_JARS[0]}"
WALLET=$(api "$WINNER_JAR" "$API/wallet")
echo "$WALLET" | python3 -c "
import sys, json
w = json.load(sys.stdin)
print(f\"    available={w['available']} pending={w['pending']} token_id={w['token_id']}\")
"
LEDGER=$(api "$WINNER_JAR" "$API/wallet/ledger")
NLEDGER=$(echo "$LEDGER" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))")
ok "ledger has $NLEDGER entries"

say "11. Reconciliation: cached balance == computed ledger balance"
REC=$(api "$WINNER_JAR" "$API/wallet/reconciliation")
echo "$REC" | python3 -c "
import sys, json
r = json.load(sys.stdin)
print(f\"    cached={r['cached_balance']} computed={r['computed_balance']} ok={r['ok']}\")
assert r['ok'], 'LEDGER MISMATCH!'
"
ok "ledger reconciles"

say "12. Ranking reflects scores"
RANK=$(api "$WINNER_JAR" "$API/rankings/me")
echo "$RANK" | python3 -c "
import sys, json
r = json.load(sys.stdin)
print(f\"    total_score_bp={r['total_score_bp']} opc_balance={r['opc_balance']}\")
"
ok "ranking available"

say "13. Admin reconciles rewards and blockchain state"
ADMIN="$TMP/admin.jar"
login "$ADMIN" "admin@qloot.example" "AdminPass123!" >/dev/null
api "$ADMIN" "$API/admin/rewards" | python3 -c "
import sys, json
rows = json.load(sys.stdin)
print('    reward allocations:', len(rows))
for r in rows[:4]:
    print(f\"      status={r['status']} amount={r['amount']}\")
"
api "$ADMIN" "$API/blockchain/status" | python3 -c "
import sys, json
s = json.load(sys.stdin)
print(f\"    chain={s['network']} dry_run={s['dry_run']} confirmations={s['confirmations_required']}\")
"
ok "admin can reconcile"

printf '\n\033[1;32m✔ QLoot end-to-end scenario completed successfully.\033[0m\n\n'
