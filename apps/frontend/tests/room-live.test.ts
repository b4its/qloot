// @vitest-environment jsdom
import { describe, it, expect } from "vitest";
import roomPageSrc from "$routes-site/rooms/[roomId]/+page.svelte?raw";

describe("room live leaderboard and presence surface", () => {
  it("fetches /rooms/{roomId}/live and renders live leaderboard", () => {
    expect(roomPageSrc).toContain("/rooms/${roomId}/live");
    expect(roomPageSrc).toContain("liveBoard");
  });

  it("surfaces member presence status within the live leaderboard", () => {
    expect(roomPageSrc).toContain("is_present");
    expect(roomPageSrc).toContain("hadir");
  });
});
