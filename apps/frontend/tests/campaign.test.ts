import { describe, it, expect } from "vitest";
import type { Course, Exam, Lesson, Quest } from "$lib/types";
import { campaignProgress, campaignSteps, nextCampaignStep } from "$lib/utils/campaign";

const course = {
  id: "c1",
  title: "Fisika Dasar",
  slug: "fisika",
  owner_id: "t1",
  is_published: false,
  lesson_count: 2,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
} as Course;

const lesson = { id: "l1", course_id: "c1", title: "Kinematika", position: 0 } as Lesson;

function exam(over: Partial<Exam> = {}): Exam {
  return {
    id: "e1",
    title: "Ujian Fisika",
    owner_id: "t1",
    duration_minutes: 60,
    status: "draft",
    is_active: false,
    passing_score_bp: 6000,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...over,
  } as Exam;
}

function quest(over: Partial<Quest> = {}): Quest {
  return {
    id: "q1",
    title: "Quest Kinematika",
    owner_id: "t1",
    status: "open",
    kind: "exam",
    top_n_winners: 3,
    reward_version: 1,
    created_at: "2026-01-01T00:00:00Z",
    ...over,
  } as Quest;
}

describe("campaign stepper (W3)", () => {
  it("marks only the course step done for a bare course", () => {
    const steps = campaignSteps({ course, lessons: [], exams: [], quests: [] });
    const byKey = Object.fromEntries(steps.map((s) => [s.key, s.state]));
    expect(byKey.course).toBe("done");
    expect(byKey.material).toBe("ready");
    expect(byKey.question).toBe("todo");
    expect(byKey.exam).toBe("todo");
    expect(byKey.quest).toBe("todo");
  });

  it("progresses the whole pipeline as artefacts appear", () => {
    const steps = campaignSteps({
      course,
      lessons: [lesson],
      exams: [exam({ question_count: 3, is_active: true })],
      quests: [quest()],
    });
    expect(steps.every((s) => s.state === "done")).toBe(true);
    expect(campaignProgress(steps)).toBe(1);
    expect(nextCampaignStep(steps)).toBeNull();
  });

  it("points the next action at the first unfinished step", () => {
    const steps = campaignSteps({
      course,
      lessons: [lesson],
      exams: [],
      quests: [],
    });
    const next = nextCampaignStep(steps);
    expect(next?.key).toBe("question");
    expect(campaignProgress(steps)).toBe(0.4);
  });

  it("treats a finalised quest as a completed quest step", () => {
    const steps = campaignSteps({
      course,
      lessons: [lesson],
      exams: [exam({ question_count: 1, is_active: true })],
      quests: [quest({ status: "finalized" })],
    });
    expect(steps.find((s) => s.key === "quest")?.state).toBe("done");
  });

  it("does not mark an unpublished exam as done", () => {
    const steps = campaignSteps({
      course,
      lessons: [lesson],
      exams: [exam({ question_count: 2, is_active: false })],
      quests: [],
    });
    expect(steps.find((s) => s.key === "question")?.state).toBe("done");
    expect(steps.find((s) => s.key === "exam")?.state).toBe("ready");
  });
});
