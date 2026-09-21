<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { auth, hasRole } from "$lib/stores/auth";
  import { api, ApiError } from "$lib/api/client";
  import Icon from "$lib/components/Icon.svelte";
  import type { TeacherAnalytics } from "$lib/types";
  import { bpToPercent } from "$lib/utils/format";
  import { teacherNav } from "$lib/data/role-nav";

  // Redirect once auth has resolved; a mount-only check missed the case where
  // auth was still loading, briefly exposing the panel to non-teachers.
  $: if (!$auth.loading && !hasRole($auth.user, "teacher")) goto("/login");

  let analytics: TeacherAnalytics | null = null;
  let error = "";

  // The hub shows every teacher section except the "Ringkasan" entry (this page).
  const links = teacherNav.filter((l) => l.href !== "/teacher");

  onMount(async () => {
    try {
      analytics = await api.get<TeacherAnalytics>("/teacher/analytics");
    } catch (e) {
      error = e instanceof ApiError ? e.message : "";
    }
  });
</script>

<svelte:head><title>Panel Guru — QLoot</title></svelte:head>

<div class="mx-auto max-w-7xl px-4 py-12 sm:px-6">
  <p class="mono-label">Panel Guru</p>
  <h1 class="mt-2 font-display text-4xl font-bold">Kelola pembelajaran</h1>
  <p class="mt-2 muted">Buat materi, jalankan ujian, dan pantau kemajuan siswa.</p>

  {#if analytics}
    <div class="mt-6 grid gap-4 sm:grid-cols-3 lg:grid-cols-6">
      {#each [{ l: "Ujian", v: String(analytics.exams), i: "file-pen" }, { l: "Dinilai", v: String(analytics.graded_attempts), i: "check-double" }, { l: "Rata-rata", v: bpToPercent(analytics.average_score_bp), i: "chart-line" }, { l: "Kelulusan", v: bpToPercent(analytics.pass_rate_bp), i: "award" }, { l: "Quest", v: String(analytics.quests), i: "trophy" }, { l: "OPC dibagi", v: String(analytics.opc_awarded), i: "gem" }] as s}
        <div class="card">
          <div class="flex items-center justify-between">
            <span class="mono-label">{s.l}</span>
            <Icon name={s.i} size="13px" class="text-primary" />
          </div>
          <p class="mt-2 font-display text-2xl font-bold">{s.v}</p>
        </div>
      {/each}
    </div>
  {/if}

  <div class="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
    {#each links as l}
      <a href={l.href} class="card lift block">
        <span class="tile-cool h-11 w-11">
          <Icon name={l.icon} size="18px" />
        </span>
        <h2 class="mt-3 font-display text-lg font-bold">{l.label}</h2>
        <p class="mt-1 text-sm muted">{l.desc}</p>
      </a>
    {/each}
  </div>
</div>
