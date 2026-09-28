import type { Attempt, Course, Exam, Progress, Quest, Reward, Task } from "$lib/types";

/** One actionable item on the student's mission feed. */
export interface Mission {
  id: string;
  kind: "resume" | "exam" | "quest" | "task" | "settlement";
  title: string;
  description: string;
  href: string;
  /** Lower sorts first. In-progress work and near deadlines lead. */
  priority: number;
  /** Null when the item has no deadline. */
  dueAt: string | null;
  tone: "action" | "urgent" | "reward";
}

export interface MissionInput {
  courses: Course[];
  progress: Progress[];
  exams: Exam[];
  attempts: Attempt[];
  quests: Quest[];
  tasks: Task[];
  completions: { task_id: string }[];
  rewards: Reward[];
  now?: Date;
}

export interface MissionState {
  /** A course with at least one lesson that is not fully completed. */
  nextCourse: Course | null;
  /** Exam currently being worked on, if any (must be resumed). */
  activeAttempt: { attempt: Attempt; exam: Exam } | null;
}

function ms(iso: string | null | undefined): number | null {
  if (!iso) return null;
  const value = new Date(iso).getTime();
  return Number.isNaN(value) ? null : value;
}

function hoursUntil(iso: string | null | undefined, now: Date): number | null {
  const target = ms(iso);
  if (target === null) return null;
  return (target - now.getTime()) / 3_600_000;
}

/** Exam availability derived exactly like the exam hub. */
export function examAvailability(exam: Exam, now = new Date()): "open" | "upcoming" | "closed" {
  if (!exam.is_active) return "closed";
  const closes = ms(exam.closes_at);
  if (closes !== null && now.getTime() > closes) return "closed";
  const opens = ms(exam.opens_at);
  if (opens !== null && now.getTime() < opens) return "upcoming";
  return "open";
}

/** Count completed lessons per course. */
export function completedByCourse(progress: Progress[]): Record<string, number> {
  return progress.reduce<Record<string, number>>((acc, p) => {
    if (p.completed) acc[p.course_id] = (acc[p.course_id] ?? 0) + 1;
    return acc;
  }, {});
}

/** The next course to continue: has lessons, not yet finished, most progress first. */
export function nextCourseFor(
  courses: Course[],
  progress: Progress[],
  now = new Date(),
): Course | null {
  void now;
  const done = completedByCourse(progress);
  return (
    courses
      .filter((c) => (c.lesson_count ?? 0) > 0 && (done[c.id] ?? 0) < (c.lesson_count ?? 0))
      .sort(
        (a, b) =>
          (done[b.id] ?? 0) / (b.lesson_count || 1) - (done[a.id] ?? 0) / (a.lesson_count || 1),
      )[0] ?? null
  );
}

/** An exam attempt that is still in progress and must be resumed. */
export function activeAttemptFor(
  attempts: Attempt[],
  exams: Exam[],
): MissionState["activeAttempt"] {
  const byId = new Map(exams.map((e) => [e.id, e]));
  for (const attempt of attempts) {
    if (attempt.status !== "in_progress") continue;
    const exam = byId.get(attempt.exam_id);
    if (exam) return { attempt, exam };
  }
  return null;
}

function examMission(exam: Exam, now: Date): Mission {
  const availability = examAvailability(exam, now);
  const closes = hoursUntil(exam.closes_at, now);
  const opens = hoursUntil(exam.opens_at, now);
  if (availability === "closed") {
    return {
      id: `exam-${exam.id}`,
      kind: "exam",
      title: exam.title,
      description: "Ujian ditutup",
      href: `/exams/${exam.id}`,
      priority: 90,
      dueAt: exam.closes_at ?? null,
      tone: "action",
    };
  }
  if (availability === "upcoming") {
    return {
      id: `exam-${exam.id}`,
      kind: "exam",
      title: exam.title,
      description:
        opens !== null && opens > 0
          ? `Dibuka dalam ${Math.max(1, Math.round(opens))} jam`
          : "Akan dibuka",
      href: `/exams/${exam.id}`,
      priority: 40,
      dueAt: exam.opens_at ?? null,
      tone: "action",
    };
  }
  const urgent = closes !== null && closes <= 24;
  return {
    id: `exam-${exam.id}`,
    kind: "exam",
    title: exam.title,
    description:
      closes !== null && closes >= 0
        ? `Tutup dalam ${Math.max(1, Math.round(closes))} jam`
        : "Siap dikerjakan",
    href: `/exams/${exam.id}`,
    priority: urgent ? 5 : 20,
    dueAt: exam.closes_at ?? null,
    tone: urgent ? "urgent" : "action",
  };
}

function questMission(quest: Quest, now: Date): Mission | null {
  if (quest.status !== "open") return null;
  const closes = hoursUntil(quest.closes_at, now);
  const urgent = closes !== null && closes >= 0 && closes <= 24;
  return {
    id: `quest-${quest.id}`,
    kind: "quest",
    title: quest.title,
    description:
      closes !== null && closes >= 0
        ? `Batas ${Math.max(1, Math.round(closes))} jam`
        : "Quest terbuka",
    href: `/quests#quest-${quest.id}`,
    priority: urgent ? 15 : 35,
    dueAt: quest.closes_at ?? null,
    tone: urgent ? "urgent" : "action",
  };
}

function taskMissions(tasks: Task[], completions: { task_id: string }[], now: Date): Mission[] {
  const done = new Set(completions.map((c) => c.task_id));
  return tasks
    .filter((t) => !done.has(t.id))
    .map((task) => {
      const closes = hoursUntil(task.ends_at, now);
      const urgent = closes !== null && closes >= 0 && closes <= 24;
      return {
        id: `task-${task.id}`,
        kind: "task" as const,
        title: task.title,
        description: `+${task.reward_amount} OPT · ${
          closes !== null && closes >= 0
            ? `${Math.max(1, Math.round(closes))} jam lagi`
            : "tersedia"
        }`,
        href: `/tasks#task-${task.id}`,
        priority: urgent ? 10 : 45,
        dueAt: task.ends_at ?? null,
        tone: urgent ? ("urgent" as const) : ("action" as const),
      };
    });
}

function settlementMissions(rewards: Reward[]): Mission[] {
  return rewards
    .filter((r) => r.status === "pending" || r.status === "failed")
    .slice(0, 3)
    .map((reward) => ({
      id: `reward-${reward.id}`,
      kind: "settlement" as const,
      title: `Hadiah ${reward.amount} OPT`,
      description:
        reward.status === "pending"
          ? "Menunggu konfirmasi on-chain"
          : "Gagal — sedang ditinjau admin",
      href: "/wallet",
      priority: reward.status === "failed" ? 30 : 60,
      dueAt: null,
      tone: reward.status === "failed" ? ("urgent" as const) : ("reward" as const),
    }));
}

/**
 * Build the ordered student mission feed from already-fetched data.
 *
 * Priority order: resume in-progress exam → nearest urgent deadline → tasks →
 * learning continue → quests → pending settlement. Deterministic ties broken by
 * title so the list never reshuffles between renders.
 */
export function buildMissions(input: MissionInput): Mission[] {
  const now = input.now ?? new Date();
  const missions: Mission[] = [];

  const active = activeAttemptFor(input.attempts, input.exams);
  if (active) {
    missions.push({
      id: `resume-${active.attempt.id}`,
      kind: "resume",
      title: active.exam.title,
      description: "Ujian sedang dikerjakan — lanjutkan sekarang",
      href: `/exams/${active.exam.id}/attempt`,
      priority: 0,
      dueAt: active.attempt.expires_at ?? null,
      tone: "urgent",
    });
  }

  const attemptedExamIds = new Set(input.attempts.map((a) => a.exam_id));
  for (const exam of input.exams) {
    if (attemptedExamIds.has(exam.id)) continue;
    missions.push(examMission(exam, now));
  }

  missions.push(...taskMissions(input.tasks, input.completions, now));

  const course = nextCourseFor(input.courses, input.progress, now);
  if (course) {
    const doneCount = completedByCourse(input.progress)[course.id] ?? 0;
    const total = course.lesson_count ?? 0;
    missions.push({
      id: `resume-course-${course.id}`,
      kind: "resume",
      title: course.title,
      description: `Lanjutkan belajar · ${doneCount}/${total} materi selesai`,
      href: `/learning/${course.id}`,
      priority: 50,
      dueAt: null,
      tone: "action",
    });
  }

  for (const quest of input.quests) {
    const mission = questMission(quest, now);
    if (mission) missions.push(mission);
  }

  missions.push(...settlementMissions(input.rewards));

  return missions.sort((a, b) => {
    if (a.priority !== b.priority) return a.priority - b.priority;
    return a.title.localeCompare(b.title);
  });
}

/** The single most important next action, or null when nothing is pending. */
export function primaryMission(missions: Mission[]): Mission | null {
  return missions[0] ?? null;
}
