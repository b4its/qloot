<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { api, apiGetPaged, ApiError } from "$lib/api/client";
  import type { User } from "$lib/types";
  import { formatDate } from "$lib/utils/format";
  import { auth, hasRole } from "$lib/stores/auth";
  import Pagination from "$lib/components/Pagination.svelte";
  import Icon from "$lib/components/Icon.svelte";
  import PageHeader from "$lib/components/PageHeader.svelte";
  import PageAlerts from "$lib/components/PageAlerts.svelte";
  import ConfirmDialog from "$lib/components/ConfirmDialog.svelte";
  import FilterChips from "$lib/components/FilterChips.svelte";
  import SearchInput from "$lib/components/SearchInput.svelte";

  $: if (!$auth.loading && !hasRole($auth.user, "admin")) goto("/login");

  const PAGE = 20;
  let users: User[] = [];
  let error = "";
  let message = "";
  let loading = true;
  let busy = "";
  let page = 1;
  let total: number | undefined = undefined;
  let query = "";
  let roleFilter: "all" | "student" | "teacher" | "admin" = "all";
  let statusFilter: "all" | "active" | "inactive" = "all";

  function buildQuery(): string {
    const params = new URLSearchParams();
    params.set("limit", String(PAGE));
    params.set("offset", String((page - 1) * PAGE));
    if (query.trim()) params.set("q", query.trim());
    if (roleFilter !== "all") params.set("role", roleFilter);
    if (statusFilter !== "all") params.set("is_active", String(statusFilter === "active"));
    return params.toString();
  }

  async function load() {
    if (!hasRole($auth.user, "admin")) return;
    loading = true;
    error = "";
    try {
      // AUTH-11: the backend returns X-Total-Count so pagination shows real
      // totals instead of guessing from a full page.
      const { data, total: count } = await apiGetPaged<User[]>(`/admin/users?${buildQuery()}`);
      users = data;
      total = count;
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat pengguna";
    } finally {
      loading = false;
    }
  }

  // Re-run the server query (debounced) whenever a filter or the search changes.
  let debounce: ReturnType<typeof setTimeout> | null = null;
  function refilter() {
    if (debounce) clearTimeout(debounce);
    debounce = setTimeout(() => {
      page = 1;
      void load();
    }, 200);
  }

  function resetFilters() {
    query = "";
    roleFilter = "all";
    statusFilter = "all";
    page = 1;
    void load();
  }

  $: hasFilters = query.trim() !== "" || roleFilter !== "all" || statusFilter !== "all";

  function go(delta: number) {
    const next = page + delta;
    if (next < 1 || (delta > 0 && total !== undefined && next > Math.ceil(total / PAGE))) return;
    page = next;
    load();
  }

  async function toggleActive(u: User) {
    error = "";
    message = "";
    busy = u.id;
    try {
      await api.patch(`/admin/users/${u.id}/active`, { is_active: !u.is_active });
      message = `${u.email} ${u.is_active ? "dinonaktifkan" : "diaktifkan"}.`;
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal mengubah status akun";
    } finally {
      // Reload to reflect the server state; `load()` clears `error`, so restore
      // any failure message afterwards so the user can actually read it.
      const failed = error;
      await load();
      if (failed) error = failed;
      busy = "";
    }
  }

  async function deactivate(u: User) {
    deactivatingUser = u;
  }

  async function confirmDeactivate() {
    const u = deactivatingUser;
    if (!u) return;
    deactivatingUser = null;
    await toggleActive(u);
  }
  let deactivatingUser: User | null = null;

  async function setRole(u: User, role: string) {
    error = "";
    message = "";
    busy = u.id;
    try {
      await api.patch(`/admin/users/${u.id}/role`, { role });
      message = `${u.email} → ${role}`;
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal mengubah peran";
    } finally {
      // Reload to revert the select's optimistic value; keep the error visible.
      const failed = error;
      await load();
      if (failed) error = failed;
      busy = "";
    }
  }

  onMount(load);
</script>

<svelte:head><title>Pengguna | Admin | QLoot</title></svelte:head>

<div class="mx-auto max-w-7xl px-4 py-12 sm:px-6">
  <PageHeader
    eyebrow="Admin · Pengguna"
    title="Pengguna"
    subtitle="Kelola peran dan status akun pengguna platform."
    backHref="/admin"
    backLabel="Admin"
    actionHref="/admin/users/new"
    actionLabel="Tambah pengguna"
  />

  <PageAlerts {message} {error} />

  <!-- Search & filters (server-side) -->
  <div class="mt-6 flex flex-wrap items-center gap-2">
    <SearchInput
      bind:value={query}
      placeholder="Cari email atau nama..."
      label="Cari pengguna"
      oninput={refilter}
    />
    <select
      class="input text-xs !py-1.5 w-auto"
      bind:value={roleFilter}
      on:change={refilter}
      aria-label="Filter peran"
    >
      <option value="all">Semua peran</option>
      <option value="student">Siswa</option>
      <option value="teacher">Guru</option>
      <option value="admin">Admin</option>
    </select>
    <FilterChips
      value={statusFilter}
      onchange={(v) => {
        statusFilter = v as typeof statusFilter;
        refilter();
      }}
      label="Filter status akun"
      options={[
        ["all", "Semua"],
        ["active", "Aktif"],
        ["inactive", "Nonaktif"],
      ]}
    />
    {#if hasFilters}
      <button class="btn-ghost !py-1.5 text-xs" on:click={resetFilters}>Reset</button>
    {/if}
    {#if total !== undefined}
      <span class="mono-label ml-auto" data-role="filtered-total">{total} pengguna</span>
    {/if}
  </div>

  <div class="card mt-4 overflow-x-auto">
    {#if loading}
      <div class="space-y-2">
        {#each Array(6) as _}<div class="skeleton h-8"></div>{/each}
      </div>
    {:else if users.length === 0}
      <p class="py-2 muted">
        {hasFilters ? "Tidak ada pengguna yang cocok dengan filtermu." : "Belum ada pengguna."}
      </p>
    {:else}
      <table class="w-full text-sm">
        <caption class="sr-only">Daftar pengguna</caption>
        <thead class="text-left muted">
          <tr>
            <th class="py-1" scope="col">Email</th>
            <th scope="col">Nama</th>
            <th scope="col">Peran</th>
            <th scope="col">Status</th>
            <th scope="col">Bergabung</th>
            <th scope="col">Atur peran</th>
          </tr>
        </thead>
        <tbody>
          {#each users as u}
            <tr class="border-t">
              <td class="py-1">{u.email}</td>
              <td>{u.full_name}</td>
              <td>
                {#each u.roles as r}<span class="badge badge-indigo mr-1">{r}</span>{/each}
              </td>
              <td>
                <span
                  class="badge"
                  class:badge-mint={u.is_active}
                  class:badge-neutral={!u.is_active}
                >
                  {u.is_active ? "Aktif" : "Nonaktif"}
                </span>
              </td>
              <td class="text-xs muted">{formatDate(u.created_at)}</td>
              <td>
                <div class="flex items-center gap-2">
                  <select
                    class="input !py-1"
                    value={u.roles[0] ?? "student"}
                    disabled={busy === u.id}
                    aria-label={`Peran utama untuk ${u.email}`}
                    title="Menetapkan peran utama pengguna"
                    on:change={(e) => setRole(u, (e.currentTarget as HTMLSelectElement).value)}
                  >
                    <option value="student">Siswa</option>
                    <option value="teacher">Guru</option>
                    <option value="admin">Admin</option>
                  </select>
                  <button
                    class="btn-ghost !py-1"
                    on:click={() => toggleActive(u)}
                    disabled={busy === u.id}
                  >
                    {u.is_active ? "Nonaktifkan" : "Aktifkan"}
                  </button>
                  {#if u.is_active}
                    <button
                      class="btn-icon !text-tertiary hover:!border-tertiary"
                      on:click={() => deactivate(u)}
                      disabled={busy === u.id}
                      aria-label="Hapus pengguna"
                    >
                      <Icon name="trash" size="12px" />
                    </button>
                  {/if}
                </div>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}
  </div>

  <Pagination
    {page}
    pageSize={PAGE}
    {total}
    {loading}
    label="pengguna"
    onPrev={() => go(-1)}
    onNext={() => go(1)}
  />
</div>

{#if deactivatingUser}
  <ConfirmDialog
    title="Nonaktifkan Akun"
    description={`Akun "${deactivatingUser.email}" tidak akan bisa masuk sampai diaktifkan kembali.`}
    confirmLabel="Ya, Nonaktifkan"
    onConfirm={confirmDeactivate}
    close={() => (deactivatingUser = null)}
  />
{/if}
