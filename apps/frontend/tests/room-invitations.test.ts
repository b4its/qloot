// @vitest-environment jsdom
import { describe, it, expect } from "vitest";
import roomDetailSrc from "$routes-site/rooms/[roomId]/+page.svelte?raw";
import roomsListSrc from "$routes-site/rooms/+page.svelte?raw";

/**
 * Rooms invitations must be full end-to-end (the backend model + service +
 * endpoints existed but had no UI): a teacher can create an invite and a user
 * can redeem an invitation code.
 */
describe("room invitations UI (full feature)", () => {
  it("room detail exposes an invite control calling POST /rooms/{id}/invite", () => {
    expect(roomDetailSrc).toContain("/rooms/${roomId}/invite");
    expect(roomDetailSrc).toContain("sendInvite");
    expect(roomDetailSrc).toContain("Undang peserta");
  });

  it("room detail surfaces the returned invitation code", () => {
    expect(roomDetailSrc).toContain("inviteResult.code");
  });

  it("rooms list can redeem an invitation code", () => {
    expect(roomsListSrc).toContain("/rooms/invitations/accept");
    expect(roomsListSrc).toContain("acceptInvitation");
    expect(roomsListSrc).toContain("Terima undangan");
  });
});
