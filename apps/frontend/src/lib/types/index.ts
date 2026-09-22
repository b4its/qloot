/** Shared API types (mirroring the FastAPI schemas). */

export interface User {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  chain_user_ref: string;
  avatar_url?: string | null;
  created_at: string;
  roles: string[];
  class_code?: string | null;
  class_type?: string | null;
}

export interface SessionInfo {
  id: string;
  user_agent?: string | null;
  ip_address?: string | null;
  created_at: string;
  expires_at: string;
  revoked_at?: string | null;
}

export interface Course {
  id: string;
  title: string;
  slug: string;
  description?: string | null;
  owner_id: string;
  owner_name?: string | null;
  is_published: boolean;
  cover_url?: string | null;
  subject?: string | null;
  class_code?: string | null;
  class_type?: string | null;
  lesson_count?: number;
  created_at: string;
  updated_at: string;
}

export interface Lesson {
  id: string;
  course_id: string;
  title: string;
  content_md?: string | null;
  video_url?: string | null;
  position: number;
  is_published: boolean;
}

export interface Progress {
  id: string;
  lesson_id: string;
  course_id: string;
  progress_percent: number;
  completed: boolean;
  completed_at?: string | null;
}

export interface Room {
  id: string;
  name: string;
  code: string;
  owner_id: string;
  course_id?: string | null;
  status: string;
  max_participants: number;
  is_public: boolean;
  opens_at?: string | null;
  closes_at?: string | null;
  created_at: string;
}

export interface QuestionOption {
  id: string;
  label: string;
  text: string;
  position: number;
  /** Only revealed to the exam owner/admin, or in the graded review. */
  is_correct?: boolean | null;
}

export interface Question {
  id: string;
  exam_id?: string | null;
  prompt: string;
  correct_answer?: string | null;
  max_score_bp: number;
  position: number;
  /** "essay" (AI-graded) or "multiple_choice" (deterministic). */
  qtype: string;
  source: string;
  review_status: string;
  options?: QuestionOption[];
}

export interface Exam {
  id: string;
  title: string;
  owner_id: string;
  room_id?: string | null;
  course_id?: string | null;
  duration_minutes: number;
  status: string;
  is_active: boolean;
  passing_score_bp: number;
  opens_at?: string | null;
  closes_at?: string | null;
  created_at: string;
  updated_at: string;
  /** Question composition — lets the UI classify an exam as multiple-choice,
   * essay or mixed without fetching every question. */
  question_count?: number;
  mc_count?: number;
  essay_count?: number;
  questions?: Question[];
}

export interface Attempt {
  id: string;
  exam_id: string;
  user_id: string;
  attempt_number: number;
  status: string;
  score_bp?: number | null;
  passed?: boolean | null;
  started_at: string;
  submitted_at?: string | null;
  graded_at?: string | null;
}

export interface Answer {
  id: string;
  question_id: string;
  answer_text?: string | null;
  score_bp?: number | null;
  max_score_bp: number;
  feedback?: string | null;
  similarity_bp?: number | null;
}

export interface QuestRule {
  rank: number;
  reward_amount: number;
  min_score_bp?: number | null;
}

export interface Quest {
  id: string;
  title: string;
  description?: string | null;
  owner_id: string;
  room_id?: string | null;
  exam_id?: string | null;
  status: string;
  kind: string;
  top_n_winners: number;
  reward_version: number;
  opens_at?: string | null;
  closes_at?: string | null;
  finalized_at?: string | null;
  created_at: string;
  rules?: QuestRule[];
}

export interface Winner {
  rank: number;
  user_id: string;
  score_bp: number;
  submitted_at: string;
  reward_key: string;
  reward_amount: number;
}

export interface Task {
  id: string;
  title: string;
  description?: string | null;
  kind: string;
  reward_amount: number;
  is_active: boolean;
  starts_at?: string | null;
  ends_at?: string | null;
  created_at: string;
}

export interface Wallet {
  user_id: string;
  token_id: number;
  available: number;
  pending: number;
  /** The caller's own personal withdrawal wallet (never the platform address). */
  withdrawal_address?: string | null;
  network?: string | null;
}

export interface AssetBalance {
  asset: string;
  name: string;
  symbol: string;
  balance: number;
  role: string;
}

export interface WalletAssets {
  user_id: string;
  network?: string | null;
  assets: AssetBalance[];
}

export interface LedgerEntry {
  id: string;
  entry_type: string;
  amount: number;
  balance_after: number;
  reference_type: string;
  reference_id: string;
  description?: string | null;
  created_at: string;
}

export interface Reward {
  id: string;
  reward_key: string;
  reward_type: string;
  rank?: number | null;
  amount: number;
  status: string;
  quest_id?: string | null;
  task_id?: string | null;
  created_at: string;
  /** Present on the admin rewards listing. */
  user_id?: string;
  token_id?: number;
  error_message?: string | null;
  blockchain_transaction_id?: string | null;
}

export interface AssetInfo {
  name: string;
  symbol: string;
  address?: string | null;
  role?: string;
}

export interface BlockchainStatus {
  dry_run: boolean;
  network: string;
  chain_id: number;
  token_id: number;
  confirmations_required: number;
  /** Legacy single-contract fields (= OPT); only on the admin status endpoint. */
  contract_address?: string | null;
  treasury_address?: string | null;
  /** Per-asset addresses (OPT/QTC/ORT/ORX); only on the admin status endpoint. */
  assets?: Record<string, AssetInfo>;
}

export interface BlockchainTx {
  id: string;
  method: string;
  status: string;
  network: string;
  chain_id: number;
  transaction_hash?: string | null;
  block_number?: number | null;
  confirmation_count: number;
  explorer_url?: string | null;
  created_at: string;
}

export interface RankingEntry {
  user_id: string;
  rank: number;
  score_bp: number;
  opc_earned: number;
  display_name?: string | null;
  duration_seconds?: number | null;
  submitted_at?: string | null;
}

export interface RankingResponse {
  scope: string;
  scope_id?: string;
  entries: RankingEntry[];
}

export interface RankingMe {
  user_id: string;
  total_score_bp: number;
  opc_balance: number;
  rank?: number;
  xp?: number;
  level?: number;
  level_progress?: number;
}

export interface XpBreakdown {
  exams: number;
  quests: number;
  tasks: number;
  badges: number;
}

export interface GamificationProfile {
  user_id: string;
  xp: number;
  level: number;
  xp_into_level: number;
  xp_for_next_level: number;
  progress: number;
  breakdown: XpBreakdown;
  quest_wins: number;
  tasks_completed: number;
}

export interface LevelEntry {
  rank: number;
  user_id: string;
  display_name?: string | null;
  xp: number;
  level: number;
}

export interface LevelLeaderboard {
  scope: string;
  entries: LevelEntry[];
}

export interface Material {
  id: string;
  owner_id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  status: string;
  created_at: string;
}

export interface Notification {
  id: string;
  kind: string;
  title: string;
  body?: string | null;
  data?: Record<string, unknown> | null;
  read_at?: string | null;
  created_at: string;
}

export interface Badge {
  code: string;
  name: string;
  description?: string | null;
  icon: string;
  points: number;
}

export interface UserBadge {
  badge: Badge;
  awarded_at: string;
  meta?: Record<string, unknown> | null;
}

export interface Certificate {
  id: string;
  credential_id: string;
  verification_hash: string;
  course_id: string;
  course_title: string;
  recipient_name: string;
  issued_by: string;
  edition_number: number;
  edition_total: number;
  issued_at: string;
  revoked_at?: string | null;
  revoked_reason?: string | null;
}

export interface CertificateVerify {
  valid: boolean;
  credential_id: string;
  course_title?: string | null;
  recipient_name?: string | null;
  issued_by?: string | null;
  issued_at?: string | null;
  verification_hash?: string | null;
}

export interface LiveEntry {
  rank: number;
  user_id: string;
  display_name?: string | null;
  score_bp: number;
  is_present: boolean;
}

export interface RoomMember {
  id: string;
  room_id: string;
  user_id: string;
  role: string;
  is_present: boolean;
  joined_at: string;
  display_name?: string | null;
}

export interface RoomEvent {
  id: string;
  event_type: string;
  payload?: Record<string, unknown> | null;
  created_at: string;
}

export interface SummaryResult {
  summary: string;
  key_points: string[];
}

export interface AskResult {
  answer: string;
  confidence_bp: number;
}

/** Reference to an enqueued AI generation job. */
export interface GenerationJob {
  job_id: string;
  status: string;
}

/** Polled AI job status. */
export interface AIJob {
  id: string;
  kind: string;
  status: string;
  attempts: number;
  error_code?: string | null;
  error_message?: string | null;
  created_at: string;
  finished_at?: string | null;
}

export interface TeacherAnalytics {
  exams: number;
  graded_attempts: number;
  average_score_bp: number;
  pass_rate_bp: number;
  quests: number;
  winners: number;
  opc_awarded: number;
}

export interface SubmissionRow {
  answer_id: string;
  exam_id: string;
  exam_title: string;
  attempt_id: string;
  student_id: string;
  /** The student's display name. */
  student_name?: string | null;
  question_id: string;
  /** "essay" | "multiple_choice" */
  qtype: string;
  prompt: string;
  answer_text?: string | null;
  /** For MC: the human-readable text of the chosen option. */
  answer_display?: string | null;
  /** For MC: the correct option label (A/B/…). */
  correct_answer?: string | null;
  /** For MC: the human-readable text of the correct option. */
  correct_display?: string | null;
  /** For MC: whether the answer was correct (null for essays / ungraded). */
  is_correct?: boolean | null;
  score_bp?: number | null;
  max_score_bp: number;
  feedback?: string | null;
  similarity_bp?: number | null;
}

/** One answered question inside a per-student exam review. */
export interface ReviewAnswer {
  question_id: string;
  position: number;
  qtype: string;
  prompt: string;
  answer_text?: string | null;
  answer_display?: string | null;
  correct_answer?: string | null;
  correct_display?: string | null;
  /** Only meaningful for MC (null for essays / ungraded attempts). */
  is_correct?: boolean | null;
  score_bp?: number | null;
  max_score_bp: number;
  feedback?: string | null;
}

export interface ExamResultRow {
  id: string;
  exam_id: string;
  user_id: string;
  attempt_number: number;
  status: string;
  score_bp?: number | null;
  passed?: boolean | null;
  started_at: string;
  submitted_at?: string | null;
  graded_at?: string | null;
  display_name?: string | null;
}

export interface ExamResultReviewRow extends ExamResultRow {
  answers: ReviewAnswer[];
}

export interface ExamResultsReview {
  exam: Exam;
  results: ExamResultReviewRow[];
}

// --- Career guidance (simulated) ------------------------------------------
export interface GradeRow {
  id?: string | null;
  subject: string;
  grade: number;
  term: string;
}

export interface Insight {
  kind: string;
  title: string;
  detail: string;
}

export interface AcademicDashboard {
  average: number;
  strong_subject?: string | null;
  weak_subject?: string | null;
  subjects: { subject: string; grade: number }[];
  trend: { month: string; value: number }[];
  radar: { dimension: string; value: number }[];
  insights: Insight[];
}

export interface Personality {
  openness: number;
  conscientiousness: number;
  extraversion: number;
  agreeableness: number;
  neuroticism: number;
  summary?: string | null;
  created_at: string;
}

export interface Recommendation {
  id: string;
  major: string;
  fit_score: number;
  academic_fit: number;
  personality_fit: number;
  rationale?: string | null;
  universities?: string[] | null;
  admission_paths?: string[] | null;
  skills?: string[] | null;
  careers?: string[] | null;
  rank: number;
  status: string;
}

export interface Milestone {
  id: string;
  title: string;
  description?: string | null;
  period: string;
  position: number;
  progress_percent: number;
  status: string;
  tasks?: string[] | null;
}

export interface Counselor {
  name: string;
  role: string;
  focus: string;
}

/** A student whose study-path plan awaits the counselor's approval. */
export interface PendingReview {
  user_id: string;
  display_name: string;
  top_major: string;
  count: number;
}

export interface Consultation {
  id: string;
  counselor: string;
  topic: string;
  scheduled_at?: string | null;
  status: string;
  notes?: string | null;
  created_at: string;
}

export interface ResourceItem {
  code: string;
  category: string;
  title: string;
  description?: string | null;
  provider?: string | null;
  is_free: boolean;
  tags?: string[] | null;
}

export interface AssistantReply {
  answer: string;
  confidence_bp: number;
}
