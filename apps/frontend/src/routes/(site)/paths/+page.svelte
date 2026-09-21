<script lang="ts">
  import { onMount } from "svelte";
  import Icon from "$lib/components/Icon.svelte";
  import { reveal } from "$lib/actions/reveal";
  import { api, ApiError } from "$lib/api/client";
  import type { Course } from "$lib/types";
  import Pagination from "$lib/components/Pagination.svelte";
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
  $: totalPages = Math.max(1, Math.ceil(subjects.length / PAGE_SIZE));
  $: if (currentPage > totalPages) currentPage = 1;
  $: paged = paginate(subjects, currentPage, PAGE_SIZE);

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
      <p class="alert-error mt-6">{error}</p>
    {/if}

    {#if loading}
      <div class="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {#each Array(6) as _}<div class="skeleton h-36"></div>{/each}
      </div>
    {:else if subjects.length === 0}
      <div class="card mt-8 grid place-items-center py-16 text-center">
        <Icon name="book-open" size="28px" class="muted" />
        <p class="mt-3 font-semibold">Belum ada mata pelajaran</p>
        <p class="text-sm muted">Guru belum menambahkan pelajaran.</p>
      </div>
    {:else}
      <div class="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {#each paged as s, i}
          <a
            href={`/courses?q=${encodeURIComponent(s.name)}`}
            use:reveal={{ delay: i * 50 }}
            class="card lift block"
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
              {#if s.classes.length === 0}<span class="text-xs muted">Belum ditargetkan</span>{/if}
            </div>
          </a>
        {/each}
      </div>
      <Pagination
        page={currentPage}
        pageSize={PAGE_SIZE}
        total={subjects.length}
        {loading}
        label="mata pelajaran"
        onPrev={() => (currentPage = Math.max(1, currentPage - 1))}
        onNext={() => (currentPage = Math.min(totalPages, currentPage + 1))}
      />
    {/if}
  </div>
</div>
