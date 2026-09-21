<script lang="ts">
  import { onMount } from "svelte";
  import { api, ApiError } from "$lib/api/client";
  import type { User } from "$lib/types";
  import { formatDate } from "$lib/utils/format";
  import Pagination from "$lib/components/Pagination.svelte";

  const PAGE = 20;
  let users: User[] = [];
  let error = "";
  let message = "";
  let loading = true;
  let busy = "";
  let page = 1;
  let hasMore = false;

  async function load() {
    loading = true;
    error = "";
    try {
      users = await api.get<User[]>(`/admin/users?limit=${PAGE}&offset=${(page - 1) * PAGE}`);
      hasMore = users.length === PAGE;
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat pengguna";
    } finally {
      loading = false;
    }
  }

  function go(delta: number) {
    const next = page + delta;
    if (next < 1 || (delta > 0 && !hasMore)) return;
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
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal mengubah status akun";
      await load();
    } finally {
      busy = "";
    }
  }

  async function setRole(u: User, role: string) {
    error = "";
    message = "";
    busy = u.id;
    try {
      await api.patch(`/admin/users/${u.id}/role`, { role });
      message = `${u.email} → ${role}`;
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal mengubah peran";
      // Reload to revert the select's optimistic value.
      await load();
    } finally {
      busy = "";
    }
  }

  onMount(load);
</script>

<svelte:head><title>Pengguna — QLoot</title></svelte:head>

<div class="mx-auto max-w-7xl px-4 py-12 sm:px-6">
  <p class="mono-label">Admin · Pengguna</p>
  <h1 class="mt-2 font-display text-3xl font-bold">Pengguna</h1>
  <p class="mt-2 muted">Kelola peran dan akun pengguna platform.</p>

  {#if message}<p class="alert-ok mt-4">
      {message}
    </p>{/if}
  {#if error}
    <p class="alert-error mt-4">
      {error}
    </p>
  {/if}

  <div class="card mt-6 overflow-x-auto">
    {#if loading}
      <div class="space-y-2">
        {#each Array(6) as _}<div class="skeleton h-8"></div>{/each}
      </div>
    {:else if users.length === 0}
      <p class="py-2 muted">Belum ada pengguna.</p>
    {:else}
      <table class="w-full text-sm">
        <thead class="text-left muted">
          <tr
            ><th class="py-1">Email</th><th>Nama</th><th>Peran</th><th>Status</th><th>Bergabung</th
            ><th>Atur peran</th></tr
          >
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
    {hasMore}
    {loading}
    label="pengguna"
    onPrev={() => go(-1)}
    onNext={() => go(1)}
  />
</div>
