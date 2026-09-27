<script lang="ts">
  import Icon from "$lib/components/Icon.svelte";

  const roles = [
    {
      title: "Senior Frontend Engineer",
      loc: "Remote · Indonesia",
      type: "Penuh waktu",
      icon: "code",
      desc: "Membangun antarmuka SvelteKit yang cepat dan aksesibel.",
    },
    {
      title: "Learning Experience Designer",
      loc: "Jakarta / Hybrid",
      type: "Penuh waktu",
      icon: "pen-ruler",
      desc: "Merancang alur belajar yang menyenangkan dan terukur.",
    },
    {
      title: "Content Creator (Data & AI)",
      loc: "Remote",
      type: "Kontrak",
      icon: "chart-line",
      desc: "Menyusun materi dan soal untuk pelajaran Data & AI.",
    },
  ];

  function applyHref(title: string): string {
    const subject = encodeURIComponent(`Lamaran: ${title}`);
    return `mailto:jobs@qloot.example?subject=${subject}`;
  }

  // --- filter + search -------------------------------------------------------
  let typeFilter = "all";
  let remoteOnly = false;
  let query = "";
  $: types = [...new Set(roles.map((r) => r.type))];
  $: filtered = roles.filter((r) => {
    if (typeFilter !== "all" && r.type !== typeFilter) return false;
    if (remoteOnly && !r.loc.toLowerCase().includes("remote")) return false;
    if (query.trim()) {
      const q = query.toLowerCase().trim();
      const hay = `${r.title} ${r.loc} ${r.type} ${r.desc}`.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });
  function resetFilters() {
    typeFilter = "all";
    remoteOnly = false;
    query = "";
  }
</script>

<svelte:head><title>Karier — QLoot</title></svelte:head>

<div class="mx-auto max-w-4xl px-4 py-16 sm:px-6">
  <p class="mono-label">Karier</p>
  <h1 class="mt-2 font-display text-4xl font-bold">Bangun masa depan pendidikan bersama kami</h1>
  <p class="mt-3 muted">
    Kami mencari orang yang percaya bahwa belajar bisa menyenangkan dan terukur.
  </p>

  <!-- Filters -->
  <div class="mt-8 flex flex-wrap items-center gap-2">
    <div class="flex flex-wrap gap-1">
      <button
        type="button"
        class="btn-pill !py-1 text-xs"
        class:!border-primary={typeFilter === "all"}
        class:!text-primary={typeFilter === "all"}
        on:click={() => (typeFilter = "all")}>Semua ({roles.length})</button
      >
      {#each types as t (t)}
        <button
          type="button"
          class="btn-pill !py-1 text-xs"
          class:!border-primary={typeFilter === t}
          class:!text-primary={typeFilter === t}
          on:click={() => (typeFilter = t)}
        >
          {t} ({roles.filter((r) => r.type === t).length})
        </button>
      {/each}
      <button
        type="button"
        class="btn-pill !py-1 text-xs"
        class:!border-primary={remoteOnly}
        class:!text-primary={remoteOnly}
        aria-pressed={remoteOnly}
        on:click={() => (remoteOnly = !remoteOnly)}
      >
        <Icon name="wifi" size="10px" /> Remote
      </button>
    </div>
    <div class="relative ml-auto w-full sm:w-64">
      <Icon
        name="magnifying-glass"
        size="12px"
        class="absolute left-3 top-1/2 -translate-y-1/2 muted"
      />
      <input
        class="input text-xs !py-1.5 !pl-8 w-full"
        placeholder="Cari posisi..."
        bind:value={query}
        aria-label="Cari posisi"
      />
    </div>
  </div>

  {#if filtered.length === 0}
    <div class="card mt-6 grid place-items-center py-12 text-center">
      <p class="muted text-sm">Tidak ada posisi yang cocok dengan filtermu.</p>
      <button class="btn-ghost mt-3 !py-1 text-xs" on:click={resetFilters}>Reset Filter</button>
    </div>
  {:else}
    <div class="mt-6 space-y-4">
      {#each filtered as r (r.title)}
        <div class="card lift" data-role={r.title}>
          <div class="flex flex-wrap items-center justify-between gap-4">
            <div class="flex items-center gap-4">
              <span class="tile h-11 w-11"><Icon name={r.icon} size="17px" /></span>
              <div>
                <p class="font-semibold">{r.title}</p>
                <p class="text-xs muted">{r.loc} · {r.type}</p>
              </div>
            </div>
            <a href={applyHref(r.title)} class="btn-secondary"
              ><Icon name="paper-plane" size="12px" /> Lamar</a
            >
          </div>
          <p class="mt-3 text-sm muted">{r.desc}</p>
        </div>
      {/each}
    </div>
  {/if}
</div>
