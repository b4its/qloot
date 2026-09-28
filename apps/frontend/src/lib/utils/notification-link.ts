import type { Notification } from "$lib/types";

const CAREER_DESTINATIONS: Record<string, string> = {
  recommendation: "/career/roadmap",
  roadmap: "/career/roadmap",
  consultation: "/career/consultation",
  resources: "/career/library",
};

function value(data: Record<string, unknown>, key: string): string | null {
  const item = data[key];
  return typeof item === "string" && item.trim() ? item.trim() : null;
}

function segment(item: string): string {
  return encodeURIComponent(item);
}

/** Resolve trusted notification context into a precise internal destination. */
export function notificationLink(notification: Notification): string | null {
  const data = notification.data ?? {};
  const examId = value(data, "exam_id");
  const attemptId = value(data, "attempt_id");
  const questId = value(data, "quest_id");
  const taskId = value(data, "task_id");
  const roomId = value(data, "room_id");
  const postId = value(data, "post_id");
  const badgeCode = value(data, "code") ?? value(data, "badge_code");
  const credentialId = value(data, "credential_id");
  const careerDestination = value(data, "career_destination");

  if (examId && attemptId) {
    return `/exams/${segment(examId)}/result?attempt=${segment(attemptId)}`;
  }
  if (roomId) return `/rooms/${segment(roomId)}`;
  if (postId) return `/community#post-${segment(postId)}`;
  if (questId) return `/quests#quest-${segment(questId)}`;
  if (taskId) return `/tasks#task-${segment(taskId)}`;
  if (badgeCode) return `/badges#badge-${segment(badgeCode)}`;
  if (credentialId) return `/verify/${segment(credentialId)}`;
  if (careerDestination && CAREER_DESTINATIONS[careerDestination]) {
    return CAREER_DESTINATIONS[careerDestination];
  }

  switch (notification.kind) {
    case "reward":
      return "/wallet";
    case "quest":
      return "/quests";
    case "badge":
      return "/badges";
    case "room":
      return "/rooms";
    case "level":
      return "/ranking";
    case "community":
      return "/community";
    case "certificate":
      return "/certificates";
    default:
      return null;
  }
}
