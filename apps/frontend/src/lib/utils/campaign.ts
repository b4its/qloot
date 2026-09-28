import type { Course, Exam, Lesson, Quest } from "$lib/types";

export type CampaignStepState = "done" | "ready" | "todo";

export interface CampaignStep {
  key: "course" | "material" | "question" | "exam" | "quest";
  label: string;
  description: string;
  href: string;
  state: CampaignStepState;
  detail: string;
}

export interface CampaignInput {
  course: Course | null;
  lessons: Lesson[];
  /** Exams whose `course_id` matches this course. */
  exams: Exam[];
  /** Quests linked to any of this course's exams. */
  quests: Quest[];
}

function hasMaterials(exams: Exam[]): boolean {
  return exams.some((e) => (e.question_count ?? 0) > 0);
}

function hasPublishedExam(exams: Exam[]): boolean {
  return exams.some((e) => e.is_active);
}

function hasOpenOrFinalizedQuest(quests: Quest[]): boolean {
  return quests.some((q) => q.status === "open" || q.status === "finalized");
}

/**
 * Compute the teacher's authoring campaign stepper for one course (W3).
 *
 * The five steps mirror the real authoring pipeline:
 * course → material (lesson) → questions → published exam → quest.
 * Each step is derived from existing data, so a step is only "done" when the
 * underlying artefact actually exists (no optimistic checkboxes).
 */
export function campaignSteps(input: CampaignInput): CampaignStep[] {
  const { course, lessons, exams, quests } = input;
  const courseReady = !!course && course.title.trim().length >= 2;
  const materialDone = lessons.length > 0;
  const questionDone = hasMaterials(exams);
  const examDone = hasPublishedExam(exams);
  const questDone = hasOpenOrFinalizedQuest(quests);

  const courseHref = course ? `/teacher/subjects/${course.id}` : "/teacher/subjects";
  const examHref = exams.length > 0 ? `/teacher/exams/${exams[0].id}` : "/teacher/exams/new";
  const questHref = quests.length > 0 ? `/teacher/quests/${quests[0].id}` : "/teacher/quests/new";

  return [
    {
      key: "course",
      label: "Pelajaran",
      description: "Judul dan kelas target.",
      href: courseHref,
      state: courseReady ? "done" : "todo",
      detail: courseReady ? "Judul siap" : "Lengkapi judul pelajaran",
    },
    {
      key: "material",
      label: "Materi",
      description: "Tambah minimal satu materi.",
      href: courseHref,
      state: materialDone ? "done" : courseReady ? "ready" : "todo",
      detail: materialDone ? `${lessons.length} materi` : "Belum ada materi",
    },
    {
      key: "question",
      label: "Soal",
      description: "Buat soal dari materi (AI atau manual).",
      href: "/teacher/materials",
      state: questionDone ? "done" : materialDone ? "ready" : "todo",
      detail: questionDone ? "Soal tersedia" : "Belum ada soal",
    },
    {
      key: "exam",
      label: "Ujian",
      description: "Susun dan terbitkan ujian.",
      href: examHref,
      state: examDone ? "done" : questionDone ? "ready" : "todo",
      detail: examDone ? `${exams.length} ujian` : "Belum diterbitkan",
    },
    {
      key: "quest",
      label: "Quest",
      description: "Tautkan ujian ke quest berhadiah.",
      href: questHref,
      state: questDone ? "done" : examDone ? "ready" : "todo",
      detail: questDone ? `${quests.length} quest` : "Belum ada quest aktif",
    },
  ];
}

/** The first step that still needs work (its recommended next action). */
export function nextCampaignStep(steps: CampaignStep[]): CampaignStep | null {
  return steps.find((s) => s.state !== "done") ?? null;
}

/** Fraction of steps completed, 0..1. */
export function campaignProgress(steps: CampaignStep[]): number {
  if (steps.length === 0) return 0;
  return steps.filter((s) => s.state === "done").length / steps.length;
}
