<script lang="ts">
  import { onMount } from "svelte";
  import Icon from "$lib/components/Icon.svelte";
  import { reveal } from "$lib/actions/reveal";
  import { api, ApiError } from "$lib/api/client";
  import type { Course } from "$lib/types";
  import Pagination from "$lib/components/Pagination.svelte";
  import EmptyState from "$lib/components/EmptyState.svelte";
  import { paginate } from "$lib/utils/format";

  interface Subject {
    name: string;
    classes: string[];
    count: number;
  }

  const PAGE_SIZE = 12;
  let subjects: Subject[] = [];
  let loading = true;
  let error = "";
  let currentPage = 1;
  let query = "";
  let classFilter = "all";

  $: allClasses = [...new Set(subjects.flatMap((s) => s.classes))].sort();
  $: filtered = subjects.filter((s) => {
    if (query.trim() && !s.name.toLowerCase().includes(query.toLowerCase().trim())) return false;
    if (classFilter !== "all" && !s.classes.includes(classFilter)) return false;
    return true;
  });
  $: totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  $: if (currentPage > totalPages) currentPage = 1;
  $: paged = paginate(filtered, currentPage, PAGE_SIZE);
  $: totalCourses = subjects.reduce((sum, s) => sum + s.count, 0);

  onMount(async () => {
    try {
      const courses = await api.get<Course[]>("/courses?limit=200");
      // Group real courses by subject, collecting the classes they target.
      const seen = new Map<string, Subject>();
      for (const c of courses) {
        const name = c.subject?.trim() || "Umum";
        const e = seen.get(name) ?? { name, classes: [], count: 0 };
        e.count += 1;
        if (c.class_code && !e.classes.includes(c.class_code)) e.classes.push(c.class_code);
        seen.set(name, e);
      }
      subjects = [...seen.values()].sort((a, b) => a.name.localeCompare(b.name));
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat mata pelajaran";
    } finally {
      loading = false;
    }
  });
</script>

<svelte:head><title>Mata Pelajaran — QLoot</title></svelte:head>

<div class="dotgrid relative">
  <div class="relative z-10 mx-auto max-w-7xl px-4 py-12 sm:px-6">
    <p class="mono-label">Kurikulum</p>
    <h1 class="mt-2 font-display text-4xl font-bold">Mata pelajaran</h1>
    <p class="mt-2 max-w-2xl muted">
      Daftar mata pelajaran yang tersedia, beserta kelas tempat pelajaran tersebut dibuka.
    </p>

    {#if error}
      <p class="alert-error mt-6" role="alert" aria-live="assertive">{error}</p>
    {/if}

    {#if loading}
      <div class="mt-8 grid grid-cols-2 gap-3 sm:grid-cols-3">
        {#each Array(3) as _}<div class="skeleton h-24"></div>{/each}
      </div>
      <div class="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {#each Array(6) as _}<div class="skeleton h-36"></div>{/each}
      </div>
    {:else if subjects.length === 0}
      <EmptyState
        icon="book-open"
        title="Belum ada mata pelajaran"
        description="Guru belum menambahkan pelajaran."
      />
    {:else}
      <!-- Overview metrics -->
      <div class="mt-8 grid grid-cols-3 gap-3">
        <div class="card p-4">
          <p class="mono-label text-[10px]">Mata Pelajaran</p>
          <p class="mt-1 font-display text-3xl font-bold">{subjects.length}</p>
        </div>
        <div class="card p-4">
          <p class="mono-label text-[10px]">Total Pelajaran</p>
          <p class="mt-1 font-display text-3xl font-bold" data-role="total-lessons">
            {totalCourses}
          </p>
        </div>
        <div class="card p-4">
          <p class="mono-label text-[10px]">Kelas</p>
          <p class="mt-1 font-display text-3xl font-bold text-primary" data-role="total-classes">
            {allClasses.length}
          </p>
        </div>
      </div>

      <!-- Search & class filter -->
      <div class="mt-5 flex flex-wrap items-center gap-3">
        <div class="relative flex-1 min-w-[220px]">
          <Icon
            name="magnifying-glass"
            size="13px"
            class="absolute left-3 top-1/2 -translate-y-1/2 muted"
          />
          <input
            class="input !pl-9"
            placeholder="Cari mata pelajaran…"
            bind:value={query}
            on:input={() => (currentPage = 1)}
            aria-label="Cari mata pelajaran"
          />
        </div>
        {#if allClasses.length > 1}
          <select
            class="input !w-auto"
            bind:value={classFilter}
            on:change={() => (currentPage = 1)}
            aria-label="Filter kelas"
          >
            <option value="all">Semua kelas</option>
            {#each allClasses as c}<option value={c}>Kelas {c}</option>{/each}
          </select>
        {/if}
      </div>

      {#if filtered.length === 0}
        <div class="card mt-8 grid place-items-center py-16 text-center">
          <Icon name="magnifying-glass" size="28px" class="muted" />
          <p class="mt-3 font-semibold">Tidak ada mata pelajaran yang cocok</p>
          <p class="text-sm muted">Coba ubah pencarian atau filter kelasmu.</p>
          <button
            class="btn-ghost mt-3 !py-1 text-xs"
            on:click={() => {
              query = "";
              classFilter = "all";
            }}>Reset Filter</button
          >
        </div>
      {:else}
        <div class="mt-6 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {#each paged as s, i (s.name)}
            <a
              href={`/courses?q=${encodeURIComponent(s.name)}`}
              use:reveal={{ delay: i * 50 }}
              class="card lift block"
              data-subject={s.name}
            >
              <div class="flex items-center justify-between">
                <span class="tile h-11 w-11">
                  <Icon name="book-open-reader" size="18px" />
                </span>
                <span class="badge badge-neutral">{s.count} pelajaran</span>
              </div>
              <h2 class="mt-3 font-display text-lg font-bold">{s.name}</h2>
              <p class="mono-label mt-1">Diajarkan di kelas</p>
              <div class="mt-2 flex flex-wrap gap-1.5">
                {#each s.classes as c}<span class="badge badge-indigo">Kelas {c}</span>{/each}
                {#if s.classes.length === 0}<span class="text-xs muted">Belum ditargetkan</span
                  >{/if}
              </div>
            </a>
          {/each}
        </div>
        <Pagination
          page={currentPage}
          pageSize={PAGE_SIZE}
          total={filtered.length}
          {loading}
          label="mata pelajaran"
          onPrev={() => (currentPage = Math.max(1, currentPage - 1))}
          onNext={() => (currentPage = Math.min(totalPages, currentPage + 1))}
        />
      {/if}
    {/if}
  </div>
</div>
