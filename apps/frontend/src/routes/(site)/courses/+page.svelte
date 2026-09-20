<script lang="ts">
  import { onMount } from "svelte";
  import { api, ApiError } from "$lib/api/client";
  import type { Course } from "$lib/types";
  import { auth, hasRole } from "$lib/stores/auth";
  import Icon from "$lib/components/Icon.svelte";
  import { reveal } from "$lib/actions/reveal";

  let subjects: Course[] = [];
  let loading = true;
  let error = "";
  let query = "";
  let classFilter = "all";

  $: user = $auth.user;
  $: canManage = hasRole(user, "teacher");
  $: classes = [...new Set(subjects.map((s) => s.class_code).filter(Boolean))] as string[];
  $: filtered = subjects.filter((s) => {
    const q = query.toLowerCase();
    const matchesQuery =
      !q ||
      s.title.toLowerCase().includes(q) ||
      (s.subject ?? "").toLowerCase().includes(q) ||
      (s.owner_name ?? "").toLowerCase().includes(q);
    const matchesClass = classFilter === "all" || s.class_code === classFilter;
    return matchesQuery && matchesClass;
  });

  async function load() {
    loading = true;
    try {
      subjects = await api.get<Course[]>("/courses");
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat pelajaran";
    } finally {
      loading = false;
    }
  }

  onMount(load);
</script>

<svelte:head><title>Pelajaran — QLoot</title></svelte:head>

<div class="dotgrid relative">
  <div class="relative z-10 mx-auto max-w-7xl px-4 py-12 sm:px-6">
    <div class="flex flex-wrap items-end justify-between gap-4">
      <div>
        <p class="mono-label">Pelajaran</p>
        <h1 class="mt-2 font-display text-4xl font-bold">Daftar pelajaran</h1>
        <p class="mt-2 max-w-2xl muted">
          {#if user}
            Pelajaran yang dapat kamu akses{#if user.class_code}
              — kelas
              <span class="font-semibold text-ink"
                >{user.class_code}{user.class_type ? ` · ${user.class_type}` : ""}</span
              >{/if}.
          {:else}
            Masuk untuk melihat pelajaran sesuai kelasmu.
          {/if}
        </p>
      </div>
      {#if canManage}
        <a href="/teacher" class="btn-primary"><Icon name="plus" size="12px" /> Kelola Pelajaran</a>
      {/if}
    </div>

    <div class="mt-6 flex flex-wrap items-center gap-3">
      <div class="relative flex-1 min-w-[220px]">
        <Icon
          name="magnifying-glass"
          size="13px"
          class="absolute left-3 top-1/2 -translate-y-1/2 muted"
        />
        <input
          class="input !pl-9"
          placeholder="Cari pelajaran, mata pelajaran, atau guru…"
          bind:value={query}
          aria-label="Cari pelajaran"
        />
      </div>
      {#if classes.length > 1}
        <select class="input !w-auto" bind:value={classFilter} aria-label="Filter kelas">
          <option value="all">Semua kelas</option>
          {#each classes as c}<option value={c}>{c}</option>{/each}
        </select>
      {/if}
    </div>

    {#if error}
      <p class="alert-error mt-4">{error}</p>
    {/if}

    {#if loading}
      <div class="mt-6 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {#each Array(6) as _}<div class="skeleton h-44"></div>{/each}
      </div>
    {:else if filtered.length === 0}
      <div class="card mt-8 grid place-items-center py-16 text-center">
        <Icon name="book-open" size="28px" class="muted" />
        <p class="mt-3 font-semibold">Belum ada pelajaran</p>
        <p class="text-sm muted">
          {#if user}Guru belum menambahkan pelajaran untuk kelasmu.{:else}Masuk untuk melihat
            pelajaran kelasmu.{/if}
        </p>
      </div>
    {:else}
      <div class="mt-6 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {#each filtered as s, i}
          <a
            href={`/courses/${s.id}`}
            use:reveal={{ delay: i * 40 }}
            class="card lift flex flex-col"
          >
            <div class="flex items-center justify-between">
              <span class="brand-mark grid h-11 w-11 place-items-center rounded-sm">
                <Icon name="book-open-reader" size="17px" />
              </span>
              <span class="badge badge-indigo"
                >{s.class_code ?? "UMUM"}{s.class_type ? ` · ${s.class_type}` : ""}</span
              >
            </div>
            <h2 class="mt-3 font-display text-lg font-bold">{s.title}</h2>
            {#if s.subject}<p class="mono-label mt-1">{s.subject}</p>{/if}
            <p class="mt-2 line-clamp-2 flex-1 text-sm muted">
              {s.description ?? "Tanpa deskripsi"}
            </p>
            <div class="mono-label mt-4 flex items-center gap-3 border-t pt-3">
              <span><Icon name="user-tie" size="10px" /> {s.owner_name ?? "Guru"}</span>
              <span>·</span>
              <span><Icon name="book" size="10px" /> {s.lesson_count ?? 0} materi</span>
            </div>
          </a>
        {/each}
      </div>
    {/if}
  </div>
</div>
