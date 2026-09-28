<script lang="ts">
  import { onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { api, ApiError } from "$lib/api/client";
  import type { Course } from "$lib/types";
  import { auth, hasRole } from "$lib/stores/auth";
  import Icon from "$lib/components/Icon.svelte";
  import Pagination from "$lib/components/Pagination.svelte";
  import PageHeader from "$lib/components/PageHeader.svelte";
  import EmptyState from "$lib/components/EmptyState.svelte";
  import PageAlerts from "$lib/components/PageAlerts.svelte";
  import ConfirmDialog from "$lib/components/ConfirmDialog.svelte";
  import FilterChips from "$lib/components/FilterChips.svelte";
  import SearchInput from "$lib/components/SearchInput.svelte";
  import MetricStrip from "$lib/components/MetricStrip.svelte";

  // Redirect once auth resolves; a mount-only check could fire before the
  // session loaded, briefly exposing teacher-only UI.
  $: if (!$auth.loading && !hasRole($auth.user, "teacher")) goto("/login");

  const PAGE = 20;
  let subjects: Course[] = [];
  let loading = true;
  let error = "";
  let message = "";
  let busy = "";
  let page = 1;
  let hasMore = false;
  let query = "";
  let publishFilter: "all" | "published" | "draft" = "all";
  let classFilter = "all";
  let deletingSubject: Course | null = null;

  $: classes = [...new Set(subjects.map((s) => s.class_code).filter(Boolean))] as string[];
  $: publishedCount = subjects.filter((s) => s.is_published).length;
  $: draftCount = subjects.length - publishedCount;
  $: totalLessons = subjects.reduce((sum, s) => sum + (s.lesson_count ?? 0), 0);
  $: filtered = subjects.filter((s) => {
    if (publishFilter === "published" && !s.is_published) return false;
    if (publishFilter === "draft" && s.is_published) return false;
    if (classFilter !== "all" && s.class_code !== classFilter) return false;
    if (query.trim()) {
      const q = query.toLowerCase().trim();
      if (!s.title.toLowerCase().includes(q) && !(s.subject ?? "").toLowerCase().includes(q))
        return false;
    }
    return true;
  });

  async function load() {
    loading = true;
    error = "";
    try {
      subjects = await api.get<Course[]>(`/courses?limit=${PAGE}&offset=${(page - 1) * PAGE}`);
      hasMore = subjects.length === PAGE;
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memuat pelajaran";
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

  async function remove(s: Course) {
    deletingSubject = s;
  }

  async function confirmRemove() {
    const s = deletingSubject;
    if (!s) return;
    deletingSubject = null;
    error = "";
    message = "";
    busy = `d-${s.id}`;
    try {
      await api.delete(`/courses/${s.id}`);
      message = "Pelajaran dihapus.";
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal menghapus";
    } finally {
      busy = "";
    }
  }

  async function togglePublish(s: Course) {
    error = "";
    message = "";
    busy = `p-${s.id}`;
    try {
      await api.patch(`/courses/${s.id}`, { is_published: !s.is_published });
      await load();
    } catch (e) {
      error = e instanceof ApiError ? e.message : "Gagal memperbarui";
    } finally {
      busy = "";
    }
  }

  onMount(load);
</script>

<svelte:head><title>Pelajaran — Panel Guru — QLoot</title></svelte:head>

<div class="mx-auto max-w-5xl px-4 py-12 sm:px-6">
  <PageHeader
    eyebrow="Panel Guru · Pelajaran"
    title="Pelajaran"
    subtitle="Kelola pelajaran yang kamu ampu. Siswa di kelas yang ditargetkan otomatis dapat mengaksesnya."
    backHref="/teacher"
    backLabel="Panel Guru"
    actionHref="/teacher/subjects/new"
    actionLabel="Pelajaran baru"
  />

  <PageAlerts {message} {error} />

  {#if loading}
    <div class="mt-6 space-y-3">
      {#each Array(3) as _}<div class="skeleton h-20"></div>{/each}
    </div>
  {:else if subjects.length === 0}
    <EmptyState
      icon="chalkboard-user"
      title="Belum ada pelajaran"
      description="Buat pelajaran pertama untuk kelasmu."
      actionHref="/teacher/subjects/new"
      actionLabel="Buat pelajaran"
    />
  {:else}
    <!-- Overview metrics -->
    <MetricStrip
      metrics={[
        { label: "Total Pelajaran", value: subjects.length },
        { label: "Terbit", value: publishedCount, tone: "text-mint", role: "published-count" },
        { label: "Draf", value: draftCount, tone: "text-highlight" },
        { label: "Total Materi", value: totalLessons },
      ]}
    />

    <!-- Search & filters -->
    <div class="mt-5 flex flex-wrap items-center gap-2">
      <SearchInput bind:value={query} placeholder="Cari pelajaran..." label="Cari pelajaran" />
      <FilterChips
        options={[
          ["all", "Semua"],
          ["published", "Terbit"],
          ["draft", "Draf"],
        ]}
        bind:value={publishFilter}
        label="Filter publikasi"
      />
      {#if classes.length > 1}
        <select
          class="input text-xs !py-1.5 w-auto"
          bind:value={classFilter}
          aria-label="Filter kelas"
        >
          <option value="all">Semua kelas</option>
          {#each classes as c}<option value={c}>Kelas {c}</option>{/each}
        </select>
      {/if}
    </div>

    {#if filtered.length === 0}
      <EmptyState
        icon="magnifying-glass"
        title="Tidak ada pelajaran yang cocok"
        description="Tidak ada pelajaran yang cocok dengan filtermu."
        actionLabel="Reset Filter"
        onAction={() => {
          query = "";
          publishFilter = "all";
          classFilter = "all";
        }}
      />
    {:else}
      <div class="card mt-4 !p-0 divide-y">
        {#each filtered as s (s.id)}
          <div
            class="flex flex-wrap items-center justify-between gap-4 px-5 py-4"
            data-subject={s.id}
          >
            <div class="flex items-center gap-4">
              <span class="brand-mark grid h-11 w-11 place-items-center rounded-sm">
                <Icon name="book-open-reader" size="17px" />
              </span>
              <div>
                <div class="flex flex-wrap items-center gap-2">
                  <p class="font-semibold">{s.title}</p>
                  <span class="badge badge-indigo"
                    >Kelas {s.class_code}{s.class_type ? ` · ${s.class_type}` : ""}</span
                  >
                  {#if !s.is_published}<span class="badge badge-amber">Draf</span>{/if}
                </div>
                <p class="text-xs muted">
                  {s.subject ?? "Tanpa mata pelajaran"} · {s.lesson_count ?? 0} materi
                </p>
              </div>
            </div>
            <div class="flex items-center gap-2">
              <a href={`/teacher/subjects/${s.id}`} class="btn-ghost">
                <Icon name="pen" size="12px" /> Kelola
              </a>
              <button
                class="btn-secondary"
                on:click={() => togglePublish(s)}
                disabled={busy === `p-${s.id}`}
              >
                <Icon name={s.is_published ? "eye-slash" : "upload"} size="12px" />
                {s.is_published ? "Sembunyikan" : "Terbitkan"}
              </button>
              <button
                class="btn-icon !text-tertiary hover:!border-tertiary"
                on:click={() => remove(s)}
                disabled={busy === `d-${s.id}`}
                aria-label="Hapus"
              >
                <Icon name="trash" size="12px" />
              </button>
            </div>
          </div>
        {/each}
      </div>
    {/if}
  {/if}

  <Pagination
    {page}
    pageSize={PAGE}
    {hasMore}
    {loading}
    label="pelajaran"
    onPrev={() => go(-1)}
    onNext={() => go(1)}
  />
</div>

{#if deletingSubject}
  <ConfirmDialog
    title="Hapus Pelajaran"
    description={`Pelajaran "${deletingSubject.title}" beserta materinya akan dihapus permanen.`}
    confirmLabel="Ya, Hapus"
    onConfirm={confirmRemove}
    close={() => (deletingSubject = null)}
  />
{/if}
