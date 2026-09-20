<script lang="ts">
  import { api } from "$lib/api/client";
  import Icon from "$lib/components/Icon.svelte";

  let email = "";
  let sent = false;
  let loading = false;

  async function submit(e: Event) {
    e.preventDefault();
    loading = true;
    try {
      await api.post("/auth/forgot-password", { email });
      sent = true;
    } finally {
      loading = false;
    }
  }
</script>

<svelte:head><title>Lupa Sandi — QLoot</title></svelte:head>

<div class="relative grid min-h-[80vh] place-items-center overflow-hidden px-4 py-12">
  <div class="aurora"></div>
  <div class="relative z-10 w-full max-w-md">
    <div class="grad-border">
      <div class="card !p-7">
        <span class="grid h-11 w-11 place-items-center rounded-xl bg-primary/10 text-primary">
          <Icon name="key" size="18px" />
        </span>
        <h1 class="mt-4 font-display text-2xl font-bold">Atur ulang kata sandi</h1>
        {#if sent}
          <p class="mt-4 rounded-sm bg-secondary/10 p-3 text-sm text-secondary">
            Jika akun dengan email tersebut ada, tautan reset telah dikirim.
          </p>
        {:else}
          <p class="mt-1 text-sm muted">Masukkan emailmu dan kami akan mengirim instruksi reset.</p>
          <form class="mt-5 space-y-4" on:submit={submit}>
            <div>
              <label class="mono-label" for="email">Email</label>
              <input id="email" class="input mt-1" type="email" bind:value={email} required />
            </div>
            <button class="btn-primary w-full" type="submit" disabled={loading}>
              {#if loading}<Icon name="spinner" spin size="13px" />{:else}<Icon
                  name="paper-plane"
                  size="13px"
                />{/if}
              {loading ? "Mengirim…" : "Kirim tautan reset"}
            </button>
          </form>
        {/if}
        <p class="mt-5 text-center text-sm muted">
          <a href="/login" class="text-primary hover:underline">Kembali ke masuk</a>
        </p>
      </div>
    </div>
  </div>
</div>
