// @vitest-environment jsdom
import { describe, it, expect } from "vitest";
import questsSrc from "$routes-site/quests/+page.svelte?raw";

describe("quest full leaderboard surface", () => {
  it("quests page allows opening full quest leaderboard via /rankings/quests/{id}", () => {
    expect(questsSrc).toContain("/rankings/quests/");
    expect(questsSrc).toContain("openQuestLeaderboard");
    expect(questsSrc).toContain("questLeaderboardData");
  });
});
