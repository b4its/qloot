<script lang="ts">
  import Icon from "$lib/components/Icon.svelte";
  import { reveal } from "$lib/actions/reveal";
  import { courses, categories, formatIDR } from "$lib/data/content";

  let activeCats = new Set<string>();
  let levels = new Set<string>();
  let sort = "popular";
  let maxPrice = 1000000;

  const levelOptions = ["Pemula", "Menengah", "Lanjutan"];

  function toggle(set: Set<string>, value: string) {
    if (set.has(value)) set.delete(value);
    else set.add(value);
    // reassign for reactivity
    activeCats = new Set(activeCats);
    levels = new Set(levels);
  }

  $: filtered = courses
    .filter((c) => (activeCats.size ? activeCats.has(c.category) : true))
    .filter((c) => (levels.size ? levels.has(c.level) : true))
    .filter((c) => c.price <= maxPrice)
    .sort((a, b) => {
      if (sort === "rating") return b.rating - a.rating;
      if (sort === "price") return a.price - b.price;
      return b.students - a.students;
    });

  $: activeCount = activeCats.size + levels.size + (maxPrice < 1000000 ? 1 : 0);
  function clearAll() {
    activeCats = new Set();
    levels = new Set();
    maxPrice = 1000000;
  }
</script>

<svelte:head><title>Katalog Kursus — QLoot</title></svelte:head>

<div class="dotgrid relative">
  <div class="relative z-10 mx-auto max-w-7xl px-4 py-12 sm:px-6">
    <p class="mono-label">Katalog</p>
    <h1 class="mt-2 font-display text-4xl font-bold">Temukan kursus yang tepat</h1>
    <p class="mt-2 max-w-2xl muted">
      {courses.length} kursus dari praktisi aktif. Filter sesuai minat, level, dan anggaranmu.
    </p>

    <div class="mt-8 grid gap-8 lg:grid-cols-[260px_1fr]">
      <!-- Filters -->
      <aside class="h-fit lg:sticky lg:top-28">
        <div class="card">
          <div class="flex items-center justify-between">
            <h2 class="font-semibold">Filter</h2>
            {#if activeCount > 0}
              <button class="text-xs text-primary" on:click={clearAll}>Reset ({activeCount})</button
              >
            {/if}
          </div>

          <div class="mt-4">
            <p class="mono-label">Kategori</p>
            <div class="mt-2 flex flex-wrap gap-2">
              {#each categories as cat}
                <button
                  class="btn-pill"
                  class:!border-primary={activeCats.has(cat)}
                  class:!text-primary={activeCats.has(cat)}
                  on:click={() => toggle(activeCats, cat)}
                >
                  {cat}
                </button>
              {/each}
            </div>
          </div>

          <div class="mt-5">
            <p class="mono-label">Level</p>
            <div class="mt-2 space-y-2">
              {#each levelOptions as lv}
                <label class="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    class="h-4 w-4 rounded border-line accent-primary"
                    checked={levels.has(lv)}
                    on:change={() => toggle(levels, lv)}
                  />
                  {lv}
                </label>
              {/each}
            </div>
          </div>

          <div class="mt-5">
            <p class="mono-label">Harga maksimum</p>
            <input
              type="range"
              min="0"
              max="1000000"
              step="50000"
              bind:value={maxPrice}
              class="mt-2 w-full accent-primary"
              aria-label="Harga maksimum"
            />
            <p class="mono mt-1 text-xs muted">≤ {formatIDR(maxPrice)}</p>
          </div>

          <div class="mt-5">
            <p class="mono-label">Bahasa</p>
            <select class="input mt-2" disabled>
              <option>Bahasa Indonesia</option>
            </select>
          </div>
        </div>
      </aside>

      <!-- Results -->
      <div>
        <div class="flex flex-wrap items-center justify-between gap-3">
          <p class="text-sm muted">{filtered.length} kursus ditemukan</p>
          <label class="flex items-center gap-2 text-sm">
            <span class="mono-label">Urutkan</span>
            <select class="input !py-1.5" bind:value={sort}>
              <option value="popular">Terpopuler</option>
              <option value="rating">Rating tertinggi</option>
              <option value="price">Harga terendah</option>
            </select>
          </label>
        </div>

        {#if activeCount > 0}
          <div class="mt-3 flex flex-wrap gap-2">
            {#each [...activeCats] as c}
              <button
                class="btn-pill !border-primary !text-primary"
                on:click={() => toggle(activeCats, c)}
              >
                {c}
                <Icon name="xmark" size="10px" />
              </button>
            {/each}
            {#each [...levels] as l}
              <button
                class="btn-pill !border-primary !text-primary"
                on:click={() => toggle(levels, l)}
              >
                {l}
                <Icon name="xmark" size="10px" />
              </button>
            {/each}
          </div>
        {/if}

        {#if filtered.length === 0}
          <div class="card mt-6 grid place-items-center py-16 text-center">
            <Icon name="folder-open" size="28px" class="muted" />
            <p class="mt-3 font-semibold">Tidak ada kursus yang cocok</p>
            <p class="text-sm muted">Coba ubah filter atau reset untuk melihat semua.</p>
            <button class="btn-secondary mt-4" on:click={clearAll}>Reset filter</button>
          </div>
        {:else}
          <div class="mt-4 grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
            {#each filtered as c, i}
              <a
                href={`/courses/${c.slug}`}
                use:reveal={{ delay: i * 40 }}
                class="card lift !p-0 overflow-hidden"
              >
                <span class="block h-28" style={`background-image:${c.accent}`}>
                  <span class="grid h-full place-items-center">
                    <Icon name={c.icon} size="28px" class="text-white/90" />
                  </span>
                </span>
                <span class="block p-4">
                  <span class="flex items-center justify-between">
                    <span class="badge badge-neutral">{c.category}</span>
                    <span class="inline-flex items-center gap-1 text-xs muted">
                      <Icon name="star" class="text-highlight" size="10px" />
                      {c.rating}
                    </span>
                  </span>
                  <span class="mt-2 block font-semibold leading-snug">{c.title}</span>
                  <span class="mono-label mt-2 flex flex-wrap items-center gap-2">
                    <span>{c.level}</span><span>·</span><span>{c.weeks} mgg</span><span>·</span
                    ><span>{c.hoursPerWeek} jam/mgg</span>
                  </span>
                  <span class="mt-3 flex items-center justify-between border-t pt-3">
                    <span class="text-xs muted">{c.mentor}</span>
                    <span class="font-display text-sm font-bold">{formatIDR(c.price)}</span>
                  </span>
                </span>
              </a>
            {/each}
          </div>
        {/if}
      </div>
    </div>
  </div>
</div>
