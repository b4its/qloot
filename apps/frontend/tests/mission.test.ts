import { describe, it, expect } from "vitest";
import type { Attempt, Course, Exam, Progress, Quest, Reward, Task } from "$lib/types";
import {
  activeAttemptFor,
  buildMissions,
  examAvailability,
  nextCourseFor,
  onboardingComplete,
  onboardingSteps,
  primaryMission,
} from "$lib/utils/mission";

const NOW = new Date("2026-01-10T12:00:00Z");

function hoursFromNow(h: number): string {
  return new Date(NOW.getTime() + h * 3_600_000).toISOString();
}

function exam(over: Partial<Exam> = {}): Exam {
  return {
    id: "e1",
    title: "Ujian Fisika",
    owner_id: "t1",
    duration_minutes: 60,
    status: "published",
    is_active: true,
    passing_score_bp: 6000,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...over,
  } as Exam;
}

function attempt(over: Partial<Attempt> = {}): Attempt {
  return {
    id: "a1",
    exam_id: "e1",
    user_id: "u1",
    attempt_number: 1,
    status: "in_progress",
    started_at: "2026-01-10T11:00:00Z",
    ...over,
  } as Attempt;
}

function course(over: Partial<Course> = {}): Course {
  return {
    id: "c1",
    title: "Fisika Dasar",
    slug: "fisika",
    owner_id: "t1",
    is_published: true,
    lesson_count: 4,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...over,
  } as Course;
}

function progress(over: Partial<Progress> = {}): Progress {
  return {
    id: "p1",
    lesson_id: "l1",
    course_id: "c1",
    progress_percent: 100,
    completed: true,
    ...over,
  } as Progress;
}

function quest(over: Partial<Quest> = {}): Quest {
  return {
    id: "q1",
    title: "Kuis Kilat",
    owner_id: "t1",
    status: "open",
    kind: "exam",
    top_n_winners: 3,
    reward_version: 1,
    created_at: "2026-01-01T00:00:00Z",
    ...over,
  } as Quest;
}

function task(over: Partial<Task> = {}): Task {
  return {
    id: "t1",
    title: "Baca 1 Materi",
    kind: "daily",
    reward_amount: 10,
    is_active: true,
    created_at: "2026-01-01T00:00:00Z",
    ...over,
  } as Task;
}

function reward(over: Partial<Reward> = {}): Reward {
  return {
    id: "r1",
    reward_key: "k1",
    reward_type: "quest_rank",
    amount: 50,
    status: "pending",
    created_at: "2026-01-01T00:00:00Z",
    ...over,
  } as Reward;
}

describe("mission feed — classification", () => {
  it("classifies exam availability from window and active flag", () => {
    expect(examAvailability(exam({ is_active: false }), NOW)).toBe("closed");
    expect(examAvailability(exam({ closes_at: hoursFromNow(-1) }), NOW)).toBe("closed");
    expect(examAvailability(exam({ opens_at: hoursFromNow(5) }), NOW)).toBe("upcoming");
    expect(
      examAvailability(exam({ opens_at: hoursFromNow(-5), closes_at: hoursFromNow(5) }), NOW),
    ).toBe("open");
  });

  it("selects the next unfinished course by most progress", () => {
    const done = [
      progress({ course_id: "c1", lesson_id: "l1" }),
      progress({ course_id: "c1", lesson_id: "l2" }),
      progress({ course_id: "c2", lesson_id: "x1" }),
    ];
    const next = nextCourseFor(
      [course({ id: "c1" }), course({ id: "c2", title: "Kimia", lesson_count: 2 })],
      done,
      NOW,
    );
    // c2 is 1/2 done (50%), c1 is 2/4 done (50%) → deterministic tie resolves to first.
    expect(next?.id).toBe("c1");

    const finished = nextCourseFor([course({ id: "c1", lesson_count: 1 })], [progress()], NOW);
    expect(finished).toBeNull();
  });

  it("finds an in-progress exam attempt that must be resumed", () => {
    const active = activeAttemptFor([attempt()], [exam()]);
    expect(active?.exam.id).toBe("e1");
    expect(activeAttemptFor([attempt({ status: "graded" })], [exam()])).toBeNull();
  });
});

describe("mission feed — ordering and content", () => {
  const base = {
    courses: [course()],
    progress: [progress({ lesson_id: "l1" })],
    exams: [exam({ closes_at: hoursFromNow(48) })],
    attempts: [],
    quests: [quest()],
    tasks: [task()],
    completions: [],
    rewards: [reward()],
    now: NOW,
  };

  it("leads with the resume action when an exam is in progress", () => {
    const missions = buildMissions({ ...base, attempts: [attempt()] });
    expect(primaryMission(missions)?.kind).toBe("resume");
    expect(primaryMission(missions)?.href).toBe("/exams/e1/attempt");
  });

  it("surfaces urgent deadlines ahead of ordinary work", () => {
    const missions = buildMissions({
      ...base,
      exams: [exam({ closes_at: hoursFromNow(6) })],
    });
    const first = primaryMission(missions);
    expect(first?.tone).toBe("urgent");
    expect(first?.description).toMatch(/tutup dalam/i);
  });

  it("excludes tasks the student already completed", () => {
    const missions = buildMissions({ ...base, completions: [{ task_id: "t1" }] });
    expect(missions.some((m) => m.id === "task-t1")).toBe(false);
  });

  it("excludes exams that already have a recorded attempt", () => {
    const missions = buildMissions({
      ...base,
      attempts: [attempt({ id: "a9", status: "graded" })],
    });
    expect(missions.some((m) => m.id === "exam-e1")).toBe(false);
  });

  it("only includes open quests", () => {
    const missions = buildMissions({ ...base, quests: [quest({ status: "draft" })] });
    expect(missions.some((m) => m.kind === "quest")).toBe(false);
  });

  it("marks pending rewards as awaiting on-chain confirmation, never confirmed", () => {
    const missions = buildMissions(base);
    const settlement = missions.find((m) => m.kind === "settlement");
    expect(settlement?.description).toMatch(/menunggu konfirmasi on-chain/i);
    expect(JSON.stringify(missions)).not.toMatch(/terkonfirmasi/i);
  });

  it("links the learning mission to the course workspace", () => {
    const missions = buildMissions(base);
    const learning = missions.find((m) => m.id === "resume-course-c1");
    expect(learning?.href).toBe("/learning/c1");
    expect(learning?.description).toMatch(/1\/4 materi selesai/);
  });

  it("is deterministic for equal priority items", () => {
    const a = buildMissions(base).map((m) => m.id);
    const b = buildMissions(base).map((m) => m.id);
    expect(a).toEqual(b);
  });

  it("returns an empty feed when there is nothing to do", () => {
    const missions = buildMissions({
      courses: [],
      progress: [],
      exams: [],
      attempts: [],
      quests: [],
      tasks: [],
      completions: [],
      rewards: [],
      now: NOW,
    });
    expect(missions).toEqual([]);
    expect(primaryMission(missions)).toBeNull();
  });
});

describe("onboarding checklist (W2)", () => {
  it("marks steps done only when the real signal is present", () => {
    const steps = onboardingSteps({
      hasClass: true,
      hasCourse: false,
      hasCompletedLesson: false,
      hasEarnedReward: false,
    });
    expect(steps.map((s) => s.key)).toEqual(["class", "lesson", "reward"]);
    expect(steps.find((s) => s.key === "class")?.done).toBe(true);
    expect(steps.find((s) => s.key === "lesson")?.done).toBe(false);
    expect(onboardingComplete(steps)).toBe(false);
  });

  it("reports complete only when every step is done", () => {
    const done = onboardingSteps({
      hasClass: true,
      hasCourse: true,
      hasCompletedLesson: true,
      hasEarnedReward: true,
    });
    expect(onboardingComplete(done)).toBe(true);
  });
});
