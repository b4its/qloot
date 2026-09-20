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

export interface Question {
  id: string;
  exam_id?: string | null;
  prompt: string;
  correct_answer?: string | null;
  max_score_bp: number;
  position: number;
  qtype: string;
  source: string;
  review_status: string;
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
  withdrawal_address?: string | null;
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
}

export interface BlockchainStatus {
  dry_run: boolean;
  network: string;
  chain_id: number;
  contract_address?: string | null;
  treasury_address?: string | null;
  token_id: number;
  confirmations_required: number;
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
  // Sequential ERC-1155 token id assigned on-chain (null until assigned).
  on_chain_id?: number | null;
}

export interface UserBadge {
  badge: Badge;
  awarded_at: string;
  meta?: Record<string, unknown> | null;
}

export interface LiveEntry {
  rank: number;
  user_id: string;
  score_bp: number;
  is_present: boolean;
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
  question_id: string;
  prompt: string;
  answer_text?: string | null;
  score_bp?: number | null;
  max_score_bp: number;
  feedback?: string | null;
  similarity_bp?: number | null;
}

// --- Career guidance (simulated) ------------------------------------------
export interface GradeRow {
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
