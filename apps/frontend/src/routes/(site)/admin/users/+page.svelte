<script lang="ts">
  import { onMount } from "svelte";
  import { api, ApiError } from "$lib/api/client";
  import type { User } from "$lib/types";
  import { formatDate } from "$lib/utils/format";

  let users: User[] = [];
  let error = "";
  let message = "";
  let loading = true;
  let busy = "";

  async function load() {
    loading = true;
    error = "";
    try {
      users = await api.get<User[]>("/admin/users?limit=100");
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat pengguna";
    } finally {
      loading = false;
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

<svelte:head><title>Users — QLoot Admin</title></svelte:head>

<div class="mx-auto max-w-7xl px-4 py-12 sm:px-6">
  <p class="mono-label">Admin · Pengguna</p>
  <h1 class="mt-2 font-display text-3xl font-bold">Users</h1>
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
      <p class="py-2 muted">Tidak ada pengguna.</p>
    {:else}
      <table class="w-full text-sm">
        <thead class="text-left muted">
          <tr
            ><th class="py-1">Email</th><th>Name</th><th>Roles</th><th>Joined</th><th>Set role</th
            ></tr
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
              <td class="text-xs muted">{formatDate(u.created_at)}</td>
              <td>
                <select
                  class="input !py-1"
                  value={u.roles[0] ?? "student"}
                  disabled={busy === u.id}
                  on:change={(e) => setRole(u, (e.currentTarget as HTMLSelectElement).value)}
                >
                  <option value="student">student</option>
                  <option value="teacher">teacher</option>
                  <option value="admin">admin</option>
                </select>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}
  </div>
</div>
