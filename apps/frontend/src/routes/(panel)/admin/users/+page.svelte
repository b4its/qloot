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

  $: if (!$auth.loading && !hasRole($auth.user, "admin")) goto("/login");

  const PAGE = 20;
  let users: User[] = [];
  let error = "";
  let message = "";
  let loading = true;
  let busy = "";
  let page = 1;
  let total: number | undefined = undefined;

  async function load() {
    loading = true;
    error = "";
    try {
      // AUTH-11: the backend returns X-Total-Count so pagination shows real
      // totals instead of guessing from a full page.
      const { data, total: count } = await apiGetPaged<User[]>(
        `/admin/users?limit=${PAGE}&offset=${(page - 1) * PAGE}`,
      );
      users = data;
      total = count;
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat pengguna";
    } finally {
      loading = false;
    }
  }

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
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal mengubah status akun";
      await load();
    } finally {
      busy = "";
    }
  }

  async function deactivate(u: User) {
    if (!confirm(`Nonaktifkan akun "${u.email}"? Pengguna tidak akan bisa masuk.`)) return;
    await toggleActive(u);
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

<svelte:head><title>Pengguna — Admin — QLoot</title></svelte:head>

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
