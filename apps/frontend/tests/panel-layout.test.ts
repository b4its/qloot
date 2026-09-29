// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, cleanup, waitFor } from "@testing-library/svelte";

// Configurable page store so each test can set the current pathname. A minimal
// inline store avoids importing anything inside `vi.hoisted` (which would create
// an import-initialisation cycle).
const { pageStore } = vi.hoisted(() => {
  let value: unknown;
  const subs = new Set<(v: unknown) => void>();
  const store = {
    subscribe(fn: (v: unknown) => void) {
      subs.add(fn);
      fn(value);
      return () => subs.delete(fn);
    },
    set(v: unknown) {
      value = v;
      subs.forEach((fn) => fn(v));
    },
  };
  store.set({
    url: new URL("http://localhost:3000/teacher"),
    params: {},
    route: { id: "/teacher" },
    status: 200,
    error: null,
    data: {},
    state: {},
  });
  return { pageStore: store };
});
vi.mock("$app/stores", () => ({ page: pageStore, navigating: { subscribe: () => () => {} } }));
vi.mock("$app/navigation", () => ({ goto: vi.fn() }));

// No network: the layout only reads the auth/opt/notification stores.
const getMock = vi.fn();
vi.mock("../src/lib/api/client", () => ({
  API_BASE: "http://localhost:8000",
  ApiError: class ApiError extends Error {
    status = 0;
  },
  api: {
    get: (...a: unknown[]) => getMock(...a),
    post: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}));

import { auth } from "$lib/stores/auth";
import PanelLayout from "../src/routes/(panel)/+layout.svelte";
import PanelLayoutWithChild from "./stubs/PanelLayoutWithChild.svelte";

function setPath(path: string) {
  pageStore.set({
    url: new URL(`http://localhost:3000${path}`),
    params: {},
    route: { id: path },
    status: 200,
    error: null,
    data: {},
    state: {},
  });
}

const teacher = {
  id: "t1",
  email: "t@x.com",
  full_name: "Teacher",
  is_active: true,
  chain_user_ref: "0x0",
  created_at: new Date().toISOString(),
  roles: ["teacher"],
};
const admin = { ...teacher, id: "a1", roles: ["admin"] };

describe("panel layout", () => {
  beforeEach(() => cleanup());
  afterEach(() => auth.setUser(null));

  it("renders the teacher panel nav on /teacher", () => {
    auth.setUser(teacher);
    setPath("/teacher/subjects");
    render(PanelLayout, {});
    // Panel label + a teacher-only nav item.
    expect(screen.getAllByText(/Panel Guru/).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: /pelajaran/i }).length).toBeGreaterThan(0);
    // The panel shell has a "back to app" link, not the marketing nav.
    expect(screen.getAllByRole("link", { name: /kembali ke aplikasi/i }).length).toBeGreaterThan(0);
  });

  it("renders the admin panel nav on /admin", () => {
    auth.setUser(admin);
    setPath("/admin/users");
    render(PanelLayout, {});
    expect(screen.getAllByText(/Panel Admin/).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: /pengguna/i }).length).toBeGreaterThan(0);
  });

  it("does not render any student app nav (dashboard/learning)", () => {
    auth.setUser(teacher);
    setPath("/teacher");
    render(PanelLayout, {});
    expect(screen.queryByRole("link", { name: /^dashboard$/i })).toBeNull();
  });

  it("defers mounting the child page until the auth bootstrap resolves", async () => {
    // Reproduces the panel race: on a hard refresh the layout mounts while
    // `auth.loading` is still true and `user` is null. Child panel pages fetch
    // in `onMount(load)` and bail when `$auth.user` is unresolved, so they must
    // NOT be mounted until auth is ready — otherwise every panel page loads empty.
    let resolveMe: (u: unknown) => void = () => {};
    getMock.mockReturnValue(new Promise((res) => (resolveMe = res)));
    auth.setUser(null);
    void auth.load(); // sets loading=true and awaits the pending /auth/me
    setPath("/admin/users");

    render(PanelLayoutWithChild);

    // While auth is unresolved the child page must not be mounted.
    expect(document.querySelector("[data-test-marker]")).toBeNull();

    // Resolve the bootstrap with an admin: the shell and child become usable.
    resolveMe(admin);
    await waitFor(() => expect(document.querySelector("[data-test-marker]")).not.toBeNull());
    expect(screen.getAllByText(/Panel Admin/).length).toBeGreaterThan(0);
  });
});
